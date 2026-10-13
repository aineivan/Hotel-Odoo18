# -*- coding: utf-8 -*-
from odoo import fields, models
import socket
import logging
from odoo import models, api
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class PosOrder(models.Model):
    _inherit = 'pos.order'

    @api.model
    def print_kot_to_network(self, printer_ip, printer_port, kot_data):
        """
        Send KOT data to network printer via raw socket connection
        
        Args:
            printer_ip: IP address of the printer
            printer_port: Port number (usually 9100 for ESC/POS)
            kot_data: Dictionary containing KOT receipt data
        """
        try:
            _logger.info(f"📡 Attempting network print to {printer_ip}:{printer_port}")
            
            # Generate ESC/POS commands
            esc_pos_data = self._generate_escpos_kot(kot_data)
            
            # Send to printer via socket
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(5)  # 5 second timeout
                sock.connect((printer_ip, printer_port))
                sock.sendall(esc_pos_data)
                _logger.info(f"✅ KOT sent to {printer_ip} successfully")
                
            return {'success': True, 'message': 'KOT printed successfully'}
            
        except socket.timeout:
            _logger.error(f"❌ Connection timeout to {printer_ip}:{printer_port}")
            raise UserError(f"Printer connection timeout: {printer_ip}")
            
        except ConnectionRefusedError:
            _logger.error(f"❌ Connection refused by {printer_ip}:{printer_port}")
            raise UserError(f"Printer connection refused: {printer_ip}")
            
        except Exception as e:
            _logger.error(f"❌ Network print error: {str(e)}")
            raise UserError(f"Failed to print to network printer: {str(e)}")

    def _generate_escpos_kot(self, kot_data):
        """
        Generate ESC/POS commands for thermal printer
        
        ESC/POS command reference:
        - ESC @ : Initialize printer
        - ESC a : Center alignment
        - ESC E : Bold on/off
        - ESC d : Feed lines
        - GS V : Cut paper
        """
        ESC = b'\x1b'
        GS = b'\x1d'
        
        commands = []
        
        # Initialize printer
        commands.append(ESC + b'@')
        
        # Center alignment + Bold
        commands.append(ESC + b'a' + b'\x01')  # Center
        commands.append(ESC + b'E' + b'\x01')  # Bold ON
        commands.append(b'KITCHEN ORDER TICKET\n')
        commands.append(ESC + b'E' + b'\x00')
        
        # Station Type with emphasis
        station_text = f"{kot_data['station_type'].upper()} STATION\n"
        commands.append(ESC + b'E' + b'\x01')
        commands.append(station_text.encode('utf-8'))
        commands.append(ESC + b'E' + b'\x00')
        
        # Left alignment for rest
        commands.append(ESC + b'a' + b'\x00')
        
        # Waiter info
        if kot_data.get('waiter_name'):
            commands.append(b'Waiter: ')
            commands.append(ESC + b'E' + b'\x01')
            commands.append(kot_data['waiter_name'].encode('utf-8'))
            commands.append(ESC + b'E' + b'\x00')
            commands.append(b'\n')
        
        commands.append(f"Created By: {kot_data['cashier_name']}\n".encode('utf-8'))
        
        if kot_data.get('order_mode'):
            commands.append(f"Mode: {kot_data['order_mode']}\n".encode('utf-8'))
        
        if kot_data.get('customer_name'):
            commands.append(f"Customer: {kot_data['customer_name']}\n".encode('utf-8'))
        
        # Separator
        commands.append(b'-' * 42 + b'\n')
        
        # Order details
        commands.append(f"Order #: {kot_data['order_ref']}\n".encode('utf-8'))
        commands.append(f"Order Time: {kot_data['order_time']}\n".encode('utf-8'))
        
        if kot_data.get('floor_name'):
            commands.append(f"Floor: {kot_data['floor_name']}\n".encode('utf-8'))
        
        if kot_data.get('table_name'):
            commands.append(f"Table: {kot_data['table_name']}\n".encode('utf-8'))
        
        # Items separator
        commands.append(b'=' * 42 + b'\n')
        
        # Order lines
        for line in kot_data['orderlines']:
            commands.append(ESC + b'E' + b'\x01') 
            line_text = f"{line['quantity']}x {line['product_name']}\n"
            commands.append(line_text.encode('utf-8'))
            commands.append(ESC + b'E' + b'\x00')
            
            if line.get('attributes'):
                for attr in line['attributes']:
                    commands.append(f"  - {attr}\n".encode('utf-8'))
            
            if line.get('note'):
                commands.append(b'  Note: ')
                commands.append(ESC + b'E' + b'\x01')
                commands.append(line['note'].encode('utf-8'))
                commands.append(ESC + b'E' + b'\x00')
                commands.append(b'\n')
            
            commands.append(b'-' * 42 + b'\n')
        
        # Footer
        commands.append(b'=' * 42 + b'\n')
        commands.append(ESC + b'a' + b'\x01') 
        commands.append(f"Total Items: {kot_data['total_items']}\n".encode('utf-8'))
        commands.append(f"Printed: {kot_data['print_time']}\n".encode('utf-8'))
        
        # Feed and cut
        commands.append(ESC + b'd' + b'\x03')  
        commands.append(GS + b'V' + b'\x41' + b'\x03')  
        
        return b''.join(commands)