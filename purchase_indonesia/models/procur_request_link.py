from openerp import models, fields, api, exceptions
from psycopg2 import OperationalError

from openerp import SUPERUSER_ID
import openerp
import openerp.addons.decimal_precision as dp
from openerp.tools import float_compare, float_is_zero
from datetime import datetime, date,time
from openerp.exceptions import ValidationError
from dateutil.relativedelta import *
import calendar
from openerp import tools
import re

class InheritPurchaseRequisition(models.Model):
    _inherit = 'purchase.requisition'

    owner_id = fields.Integer('owner id')

class InheritResCompany(models.Model):

    _inherit = 'res.company'

    code = fields.Char('Code Company')


class InheritPurchaseRequest(models.Model):

    _inherit = 'purchase.request'

    complete_name =fields.Char("Complete Name", compute="_complete_name", store=True)
    type_purchase = fields.Selection([('normal','Normal'),
                                     ('urgent','Urgent')],'Purchase Type')
    type_functional = fields.Selection([('agronomy','Agronomy'),
                                     ('technic','Technic'),('general','General')],'Unit Functional')
    department_id = fields.Many2one('hr.department','Department')
    employee_id = fields.Many2one('hr.employee','Employee')
    type_location = fields.Selection([('estate','Estate'),
                                     ('ho','HO'),('ro','RO')],'Location Type')
    type_product = fields.Selection([('capital','Capital'),
                                     ('service','Service'),('product','Stockable Product')],'Location Type')
    type_budget = fields.Selection([('available','Budget Available'),('not','Budget Not Available')])

    @api.multi
    def button_approved(self):
        self.create_purchase_requisition()
        super(InheritPurchaseRequest, self).button_approved()
        return True

    @api.multi
    def create_purchase_requisition(self):
        for purchase in self:
            purchase_data = {
                'responsible':purchase.requested_by.id,
                'origin': purchase.name,
                'ordering_date': purchase.date_start,
                'owner_id' : purchase.id
            }
            res = self.env['purchase.requisition'].create(purchase_data)


        for purchaseline in self.env['purchase.request.line'].search([('request_id.id','=',self.id)]):
            purchaseline_data = {
                'product_id': purchaseline.product_id.id,
                'product_uom_id': purchaseline.product_uom_id.id,
                'product_qty' : purchaseline.product_qty,
                'schedule_date' : purchaseline.date_start,
                'requisition_id' : res.id
            }
            self.env['purchase.requisition.line'].create(purchaseline_data)

        return True

    @api.one
    @api.depends('name','date_start','company_id','department_id')
    def _complete_name(self):
        """ Forms complete name of location from parent category to child category.
        """
        fmt = '%Y-%m-%d'

        if self.name and self.date_start and self.company_id.code and self.department_id:
            date = self.date_start
            conv_date = datetime.strptime(str(date), fmt)
            month = conv_date.month
            year = conv_date.year

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

            self.complete_name = self.name + ' / ' \
                                 + self.company_id.code+' - '\
                                 +'PP'+' / '\
                                 +str(self.department_id.name)+'/'+str(month)+'/'+str(year)
        else:
            self.complete_name = self.name

        return True

    @api.multi
    @api.onchange('type_functional')
    def _onchange_department(self):
        arrDepartment = []
        if self.type_functional == 'agronomy':
            department = self.env['hr.department'].search([('name','in',['agronomi','Agronomi',
                                                                         'Agronomy','agronomy','PR & LA','Pr & La',
                                                                         'PR&LA','pr & la','pr&la'])])
            for department in department:
                arrDepartment.append(department.id)
            return {
                'domain':{
                    'department_id':[('id','in',arrDepartment)]
                }
            }
        if self.type_functional == 'technic':
            department = self.env['hr.department'].search([('name','in',['IE','transport & workshop','Transport & Workshop'])])
            for department in department:
                arrDepartment.append(department.id)
            return {
                'domain':{
                    'department_id':[('id','in',arrDepartment)]
                }
            }
        if self.type_functional == 'general':
            department = self.env['hr.department'].search([('name','in',['HR & GA','HR','GA',
                                                                         'ICT','Finance','Legal','Procurement','GIS','RO'])])
            for department in department:
                arrDepartment.append(department.id)
            return {
                'domain':{
                    'department_id':[('id','in',arrDepartment)]
                }
            }

    @api.multi
    @api.onchange('department_id')
    def _onchange_employee(self):
        #onchange employee by Department
        arrEmployee=[]
        if self.department_id:

            employee = self.env['hr.employee'].search([('department_id.id','=',self.department_id.id)])
            for employeelist in employee:
                arrEmployee.append(employeelist.id)
            return {
                'domain':{
                    'employee_id' :[('id','in',arrEmployee)]
                }
            }

    @api.multi
    @api.onchange('employee_id')
    def _onchange_department_from_employee(self):

        if self.employee_id:
           self.assigned_to = self.employee_id.parent_id.id
           self.department_id = self.employee_id.department_id.id
           self.company_id = self.employee_id.company_id.id
           department1 = self.env['hr.department'].search([('name','in',['agronomi','Agronomi','Agronomy','agronomy','PR & LA','Pr & La','PR&LA','pr & la','pr&la'])])
           department2 = self.env['hr.department'].search([('name','in',['IE','transport & workshop','Transport & Workshop'])])
           department3 = self.env['hr.department'].search([('name','in',['HR & GA','HR','GA','ICT','Finance','Legal','Procurement','GIS','RO'])])
           if department1 :
                self.type_functional = 'agronomy'
           if department2 :
                self.type_functional = 'technic'
           if department3 :
                self.type_functional = 'general'

    @api.multi
    @api.onchange('line_ids')
    def _onchange_budget_type(self):
        arrBudget = []
        for item in self.line_ids:
            if item.budget_available <= 0:
                self.type_budget = 'not'
            if item.budget_available >= 0:
                self.type_budget = 'available'
       



class InheritPurchaseRequestLine(models.Model):

    _inherit = 'purchase.request.line'
    _description = 'Inherit Purchase Request Line'

    origin = fields.Char('Ref No')
    price_per_product = fields.Float('Prod Price')
    total_price = fields.Float('Total Price',compute='_compute_total_price')
    budget_available = fields.Float('Budget Available')

    @api.multi
    @api.depends('price_per_product','product_qty')
    def _compute_total_price(self):
        if self.product_qty and self.price_per_product:
            self.total_price = self.product_qty * self.price_per_product

    @api.multi
    @api.onchange('product_id')
    def _onchange_price_pre_product(self):
        arrLisproduct = []
        arrPrice =[]
        if self.product_id:
            product = self.env['product.product'].search([('id','=',self.product_id.id)])
            for product in product:
                arrLisproduct.append(product.product_tmpl_id.id)
            product_temp = self.env['product.price.history'].search([('product_id','in',arrLisproduct)])
            for producttemp in product_temp:
                arrPrice.append(producttemp.cost)
            for price in arrPrice:
                price = float(price)
                self.price_per_product = price

    @api.multi
    @api.onchange('analytic_account_id')
    def _onchange_budget_available(self):
        arrBudget = []
        if self.analytic_account_id:
            budget = self.env['crossovered.budget.lines'].search([('analytic_account_id','=',self.analytic_account_id.id)])
            for budget in budget:
                arrBudget.append(budget.planned_amount)
            for amount in arrBudget:
                amount = float(amount)
                self.budget_available = amount




    #todo onchange product by type_product in purchase_request
    # @api.multi
    # @api.onchange('product_id')
    # def _onchange_product_id(self):
    #     arrProduct = []
    #     arrPurchase = []
    #     purchase_request = self.env['purchase.request'].search([('id','=',self.owner_id)])
    #     if self:
    #         for request in purchase_request:
    #             arrPurchase.append(request.id)
    #             print 'cobaindong'
    #             print arrPurchase

        # if self.type_product == 'consu':
        #     purchase_line = self.env['purchase.request.line'].search(['orner_id','=',self.id])
        #     for product in purchase_line:
        #         arrProduct.append(product.product_id)