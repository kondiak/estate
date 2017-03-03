from openerp import models, fields, api, exceptions
from psycopg2 import OperationalError

from openerp import SUPERUSER_ID
import openerp
import openerp.addons.decimal_precision as dp
from openerp.tools import float_compare, float_is_zero
from datetime import datetime, date,time
from openerp.tools.translate import _
from openerp.exceptions import ValidationError
from dateutil.relativedelta import *
import calendar
from openerp import tools
import re

class InheritPurchaseOrder(models.Model):

    _inherit = 'purchase.order'
    _rec_name = 'complete_name'

    delivery_term = fields.Selection([('indent','Indent'),('ready','Ready Stock')],'Term Of Delivery')
    days = fields.Float('Days Of Indent')
    companys_id = fields.Many2one('res.company','Company')
    complete_name =fields.Char("Complete Name", compute="_complete_name", store=True)
    type_location = fields.Char('Location')
    location = fields.Char('Location')
    source_purchase_request = fields.Char('Source Purchase Request')
    request_id = fields.Many2one('purchase.request','Purchase Request')
    po_no = fields.Char('Purchase order number')
    hide = fields.Boolean('Hide')
    confirmed_by = fields.Selection([
        ('fax', 'Fax'),
        ('email', 'E-Mail'),
        ('phone', 'Phone'),
        ('other','Other')])
    confirmed_by_value = fields.Char('Confirmed ByValue')
    confirmed_by_person = fields.Char('Confirmed ByPerson')
    validation_confirmed_by = fields.Boolean('Validation Confirmed By',default = False,compute='change_validation_confirmed_by')
    state = fields.Selection([
        ('draft', 'Quotation'),
        ('sent', 'RFQ Sent'),
        ('to approve', 'To Approve'),
        ('purchase', 'Purchase Order'),
        ('done', 'Done'),
        ('cancel', 'Cancelled'),('received_all','Received All'),('received_force_done','Received Force Done')
        ], string='Status', readonly=True, select=True, copy=False, default='draft', track_visibility='onchange')
    count_grn_done = fields.Integer('Count GRN Done', compute='_compute_grn_or_srn')
    count_grn_assigned = fields.Integer('Count GRN Assigned', compute='_compute_grn_or_srn')
    validation_check_confirm_vendor = fields.Boolean('Confirm Vendor')

    _defaults = {
        'hide' : False
    }

    @api.multi
    def button_confirm(self):
        self._constraint_quantity_backorder_po()
        self._update_po_no()
        super(InheritPurchaseOrder,self).button_confirm()
        self._update_shipping()
        self._update_delivery_term()
        return True

    @api.multi
    @api.depends('confirmed_by')
    def change_validation_confirmed_by(self):
        for item in self:
            if item.confirmed_by:
                item.validation_confirmed_by = True

    @api.multi
    @api.depends('picking_ids')
    def _compute_grn_or_srn(self):
        for item in self:
            request_name = item.request_id.complete_name
            arrPickingDone = []
            arrPickingAssigned = []
            done = item.env['stock.picking'].search([('pr_source','in',[request_name]),('state','=','done')])
            assigned = item.env['stock.picking'].search([('pr_source','in',[request_name]),('state','=','assigned')])
            for itemDone in done:
                arrPickingDone.append(itemDone.id)
            for itemAssign in assigned:
                arrPickingAssigned.append(itemAssign.id)
            assign_picking_done = item.env['stock.picking'].search([('id','in',arrPickingDone)])
            assign_picking_assigned = item.env['stock.picking'].search([('id','in',arrPickingAssigned)])
            picking_done = len(assign_picking_done)
            picking_assigned = len(assign_picking_assigned)

            item.count_grn_done = picking_done


            item.count_grn_assigned = picking_assigned

    @api.one
    @api.depends('po_no','name','date_order','companys_id','type_location')
    def _complete_name(self):
        """ Forms complete name of location from parent category to child category.
        """
        fmt = '%Y-%m-%d %H:%M:%S'
        if self.date_order and self.companys_id.code and self.type_location:
            date = self.date_order
            conv_date = datetime.strptime(str(date), fmt)
            month = conv_date.month
            year = conv_date.year
            location = self.type_location

            #change integer to roman
            if type(month) != type(1):
                raise TypeError, "expected integer, got %s" % type(month)
            if not 0 < month < 4000:
                raise ValueError, "Argument must be between 1 and 3999"
            ints = (1000, 900,  500, 400, 100,  90, 50,  40, 10,  9,   5,  4,   1)
            nums = ('M',  'CM', 'D', 'CD','C', 'XC','L','XL','X','IX','V','IV','I')
            result = ""
            for i in range(len(ints)):
              count = int(month / ints[i])
              result += nums[i] * count
              month -= ints[i] * count
            month = result
            po_no = ''
            if not self.po_no:
                self.complete_name = ' Draft '+self.name  + '/' \
                                 +str(month) +'/'+str(year)\
                                 +'/'+self.companys_id.code+'/'+str(self.type_location)
            elif self.po_no:
                self.complete_name = self.po_no + '/' \
                                 +str(month) +'/'+str(year)\
                                 +'/'+self.companys_id.code+'/'\
                                 +str(self.type_location)

    @api.multi
    def print_quotation(self):
        self.write({'state': "sent"})
        return self.env['report'].get_action(self, 'purchase_indonesia.report_purchase_quotation')

    @api.multi
    def print_purchase_order(self):
        return self.env['report'].get_action(self, 'purchase_indonesia.report_purchase_order')

    @api.multi
    def _update_po_no(self):
        po = self.env['purchase.order'].search([('id','=',self.id)])
        sequence_name = 'purchase.order.seq.'+self.type_location.lower()+'.'+self.companys_id.code.lower()
        purchase_data = {
            'po_no' : self.env['ir.sequence'].next_by_code(sequence_name)
        }
        po.write(purchase_data)

    @api.multi
    def _update_shipping(self):
        #update data in stock.picking
        #return : companys_id,purchase_id,type_location.pr_source
        for purchase_order in self:
            sequence_name = 'stock.grn.seq.'+self.type_location.lower()+'.'+self.companys_id.code.lower()
            purchase_data = {
                'companys_id': purchase_order.companys_id.id,
                'purchase_id': purchase_order.id,
                'type_location': purchase_order.type_location,
                'location':purchase_order.location,
                'pr_source' : purchase_order.source_purchase_request,
                'grn_no' : self.env['ir.sequence'].next_by_code(sequence_name)
            }
            self.env['stock.picking'].search([('purchase_id','=',self.id)]).write(purchase_data)
        return True

    @api.multi
    def _constraint_quantity_backorder_po(self):

        #search Purchase Tender
        requisition_id = self.env['purchase.requisition'].search([('request_id','=',self.request_id.id)]).id
        for item in self:
            if item.state == 'draft':

                for record in item.order_line:
                    requisition_line_id = self.env['purchase.requisition.line'].search([('requisition_id','=',requisition_id),
                                                                          ('product_id','=',record.product_id.id)])
                    order_line = self.env['purchase.order.line'].search([('order_id','=',self.id),
                                                                         ('product_id','=',requisition_line_id.product_id.id)]).product_qty
                    if requisition_line_id.qty_outstanding > 0 :
                        if order_line > requisition_line_id.qty_outstanding :
                            error_msg = 'Cannot Approve Back Order Cause Product Qty Is more Than Qty Outstanding'
                            raise exceptions.ValidationError(error_msg)

    @api.multi
    def _update_delivery_term(self):
        idx_ready = self.env['purchase.order.line'].search([('order_id','=',self.id),('term_of_goods','=','ready')])
        idx_indent = self.env['purchase.order.line'].search([('order_id','=',self.id),('term_of_goods','=','indent')])
        delivery_data = {
            'delivery_term' : 'ready' if len(idx_ready) >= 1 and len(idx_indent) < 1 or len(idx_ready) >= 1 and len(idx_indent) >= 1 else 'indent'
        }
        self.env['purchase.order'].search([('id','=',self.id)]).write(delivery_data)

class InheritPurchaseOrderLine(models.Model):

    _inherit = 'purchase.order.line'

    qty_request = fields.Float('Quantity Actual')
    spesification = fields.Text('Spesification')
    term_of_goods = fields.Selection([('indent','Indent'),('ready','Ready Stock')],'Term Of Goods')
    days = fields.Float('Days Of Indent')
