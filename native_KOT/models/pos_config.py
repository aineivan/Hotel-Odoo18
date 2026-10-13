from odoo import models, fields, api
from odoo.exceptions import ValidationError


class PosPrinter(models.Model):
    _inherit = 'pos.printer'

    printer_type = fields.Selection(
        selection_add=[('usb', 'USB/Local Printer')],
        ondelete={'usb': 'set default'}
    )


    @api.constrains('product_categories_ids')
    def _check_categories(self):
        for printer in self:
            if not printer.product_categories_ids:
                raise ValidationError(
                    f"Printer '{printer.name}' must have at least one product category assigned."
                )

    @api.constrains('printer_type', 'proxy_ip', 'epson_printer_ip')
    def _check_printer_config(self):
        for printer in self:
            if printer.printer_type == 'iot' and not printer.proxy_ip:
                raise ValidationError(
                    "IoT printers require a Proxy IP address")
            if printer.printer_type == 'epson_epos' and not printer.epson_printer_ip:
                raise ValidationError("Epson printers require an IP address")
