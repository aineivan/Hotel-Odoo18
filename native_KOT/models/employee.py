from odoo import fields, models, api
from odoo.exceptions import UserError
from odoo.tools.translate import _


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    is_waiter = fields.Boolean(string='Is Waiter', default=False)

    @api.model
    def _load_pos_data_fields(self, config):
        fields_list = super()._load_pos_data_fields(config)
        fields_list.append('is_waiter')
        return fields_list


class PosOrder(models.Model):
    _inherit = 'pos.order'

    waiter_id = fields.Many2one(
        'hr.employee',
        string='Waiter',
        domain=[('is_waiter', '=', True)],
    )

    kot_printed = fields.Boolean(
        string='KOT Printed',
        default=False,
        copy=False,
        help="Whether the Kitchen Order Ticket has been printed for this order.",
    )

    @api.model
    def _order_fields(self, ui_order):
        res = super()._order_fields(ui_order)

        waiter = ui_order.get('waiter_id')
        if isinstance(waiter, dict):
            res['waiter_id'] = waiter.get('id')
        elif isinstance(waiter, int):
            res['waiter_id'] = waiter
        else:
            res['waiter_id'] = False

        if ui_order.get('kot_printed'):
            res['kot_printed'] = True

        return res

    @api.model
    def _export_for_ui(self, order):
        res = super()._export_for_ui(order)
        res['waiter_id'] = order.waiter_id.id if order.waiter_id else False
        res['waiter_name'] = order.waiter_id.name if order.waiter_id else False
        res['kot_printed'] = order.kot_printed
        return res

    BLOCKED_FIELDS = {
        'lines', 'partner_id', 'waiter_id', 'note',
        'pricelist_id', 'fiscal_position_id', 'user_id',
        'table_id', 'floor_id', 'customer_count',
    }

    def write(self, vals):
        for order in self:
            if order.kot_printed and not self.env.user.has_group('point_of_sale.group_pos_manager'):
                if set(vals.keys()) & self.BLOCKED_FIELDS:
                    raise UserError(
                        _('You cannot edit an order after the KOT has been printed. '
                          'Only a POS Administrator can modify it.')
                    )
        return super().write(vals)

    def unlink(self):
        for order in self:
            if order.kot_printed and not self.env.user.has_group('point_of_sale.group_pos_manager'):
                raise UserError(
                    _('You cannot delete an order after the KOT has been printed. '
                      'Only a POS Administrator can delete it.')
                )
        return super().unlink()


class ReportPosOrder(models.Model):
    _inherit = 'report.pos.order'

    waiter_id = fields.Many2one(
        'hr.employee',
        string='Waiter',
        readonly=True
    )

    def _select(self):
        return super()._select() + ", s.waiter_id"

    def _group_by(self):
        return super()._group_by() + ", s.waiter_id"