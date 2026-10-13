# -*- coding: utf-8 -*-
from odoo import models, fields, api


class PosCategory(models.Model):
    _inherit = 'pos.category'

    is_barista = fields.Boolean(
        string="Is Barista Category",
        default=False,
        help="Check this if items in this category should appear in the Barista section of the KOT"
    )

    is_kitchen = fields.Boolean(
        string="Is Kitchen Category",
        default=False,
        help="Check this if items in this category should appear in the Kitchen section of the KOT"
    )

    @api.model
    def _load_pos_data_fields(self, config):
        fields_list = super()._load_pos_data_fields(config)  # ✅ FIX

        # ✅ avoid duplicates (important in Odoo 17)
        if 'is_barista' not in fields_list:
            fields_list.append('is_barista')
        if 'is_kitchen' not in fields_list:
            fields_list.append('is_kitchen')

        return fields_list
    
    

class PosSession(models.Model):
    _inherit = 'pos.session'

    def _loader_params_hr_employee(self):
        # Get the standard parameters for loading employees
        params = super()._loader_params_hr_employee()
        
        # Add your custom field to the 'fields' list
        if 'is_waiter' not in params['search_params']['fields']:
            params['search_params']['fields'].append('is_waiter')
            
        return params
    
    def _loader_params_pos_order(self):
        params = super()._loader_params_pos_order()

        if 'waiter_id' not in params['search_params']['fields']:
            params['search_params']['fields'].append('waiter_id')

        return params