# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo import tools, _
from odoo.exceptions import ValidationError, AccessError
import pyodbc


class BRDatabase(models.Model):
    _name = 'br_connector.database'
    _description = 'BR Database'

    name = fields.Char(string='Name of Database')
    database_host = fields.Char(string='Host')
    database_port = fields.Char(string='Port')
    database_uid = fields.Char(string='UID')
    database_passwd = fields.Char(string='Password')

    _sql_constraints = [
        ('name_uniq', 'UNIQUE (name)', _('You cannot have multiple databases wth the same name'))
    ]

    @api.one
    def action_test_connection(self):
        connection_res = self.connect_database()
        connection_res = connection_res[0]
        if connection_res:
            if 'status' in connection_res and connection_res['status'] == 200:
                self.env.user.notify_success(message=_('Connection to database {0} is successful.'.
                                                       format(self.name)),
                                             title=_('Connection Success'), sticky=True)
                connection_res['cursor'].close()
                connection_res['connection'].close()
            else:
                raise ValidationError(_('An Error was encountered: {0}'.format(connection_res['error'])))
        else:
            self.env.user.notify_danger(message=_('Connection to database {0} did not return any response'.format(self.name),
                                                  title=_('Connection Failed', sticky=True)))

    @api.one
    def connect_database(self):
        """
        This method takes the objects attributes, gets config values and creates a connection to database
        :return: a dict containing the cursor, connection, status and error.
        status 200 - successful, 500 - failure.
        """
        connection_res = {}
        connect_br_enabled = self.env['ir.config_parameter'].sudo().get_param('br_connector.connect_to_br')
        if connect_br_enabled:
            if self.name and self.database_host and self.database_port and self.database_uid and self.database_passwd:
                free_tds_path = self.env['ir.config_parameter'].sudo().get_param('br_connector.free_tds_driver_path')
                tds_version = self.env['ir.config_parameter'].sudo().get_param('br_connector.tds_version')
                if free_tds_path and tds_version:
                    quoted_connection = ';'.join(
                        [
                            'DRIVER={}'.format(free_tds_path),
                            'SERVER={}'.format(self.database_host),
                            'DATABASE={}'.format(self.name),
                            'UID={}'.format(self.database_uid),
                            'PWD={}'.format(self.database_passwd),
                            'PORT={}'.format(self.database_port),
                            'TDS_VERSION={}'.format(str(tds_version))
                        ]
                    )
                    try:
                        connection = pyodbc.connect(quoted_connection)
                        if connection and connection is not None:
                            cursor = connection.cursor()
                            connection_res.update(
                                {'cursor': cursor, 'connection': connection, 'status': 200, 'error': ''})
                    except pyodbc.Error as ex:
                        connection_res.update(
                            {'cursor': None, 'connection': None, 'status': 500, 'error': str(ex)})
                else:
                    raise ValidationError(_('No Free TDS driver path set, please set path to driver in general '
                                            'settings.'))
            else:
                raise ValidationError(_("Please make sure all database credentials are provided."))
        else:
            raise ValidationError(_("SQL connection is not enabled in general settings."))
        return connection_res


class ResConfig(models.TransientModel):
    _inherit = ['res.config.settings']

    connect_to_br = fields.Boolean(default=False, string='Connect to BR', help='Set true if you want to connect to BR.')
    free_tds_driver_path = fields.Char(string='Free TDS Driver Path')
    tds_version = fields.Float(string='TDS Version', digits=(2, 1))

    @api.model
    def get_values(self):
        res = super(ResConfig, self).get_values()
        res.update(
            connect_to_br=self.env['ir.config_parameter'].sudo().get_param(
                'br_connector.connect_to_br'),
            free_tds_driver_path=self.env['ir.config_parameter'].sudo().get_param(
                'br_connector.free_tds_driver_path'),
            tds_version=float(self.env['ir.config_parameter'].sudo().get_param('br_connector.tds_version')),
        )
        return res

    @api.multi
    def set_values(self):
        super(ResConfig, self).set_values()
        self.env['ir.config_parameter'].sudo().set_param('br_connector.connect_to_br',
                                                         self.connect_to_br)
        self.env['ir.config_parameter'].sudo().set_param('br_connector.free_tds_driver_path',
                                                         self.free_tds_driver_path)
        self.env['ir.config_parameter'].sudo().set_param('br_connector.tds_version',
                                                         self.tds_version)
