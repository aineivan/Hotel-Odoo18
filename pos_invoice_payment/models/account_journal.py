from odoo import api, models, fields
from odoo.exceptions import UserError
from odoo import _


class AccountJournal(models.Model):
    """Inherited the 'account.journal' model to add custom methods."""

    _inherit = "account.journal"

    @api.model
    def get_journal(self):
        """
        Retrieve available journals.
        Returns:
            list: A list of dictionaries containing 'id' and 'name' of each journal.
        """
        journal_list = [
            {"id": journal.id, "name": journal.name}
            for journal in self.search(
                ["|", ("type", "=", "bank"), ("type", "=", "cash")]
            )
        ]
        return journal_list

