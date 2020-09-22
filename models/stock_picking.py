# -*- coding: utf-8 -*-

from odoo import api, fields, models, tools, _
from odoo.exceptions import AccessError, UserError, ValidationError


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    aux_location_dest_id = fields.Many2one(
        comodel_name='stock.location',
        string='Ubicación Destino',
        domain=[('usage', '=', 'internal')]
    )
    code = fields.Selection(
        selection=[
            ('incoming', 'Vendors'),
            ('outgoing', 'Customers'),
            ('internal', 'Internal')],
        related="picking_type_id.code",
        string='Tipo de operación',
    )

    """
    can_validate = fields.Boolean(
        string='Puede recibir',
        compute='_compute_can_validate'
    )
    """

    def action_cancel(self):
        for line in self:
            if line.aux_location_dest_id:
                user_location_ids = ([x.id for x in line.env.user.location_ids if x])
                if not (line.location_id.id in user_location_ids):
                    msm = u"No tiene permisos para cancelar"
                    return {
                            'warning': {
                            'title': _('Inventario'),
                            'message': _(msm)
                        }
                    }
        return super(StockPicking, self).action_cancel()

    def button_validate(self):
        r = super(StockPicking, self).button_validate()
        if self.aux_location_dest_id:
            self.is_locked = not self.is_locked
            return r
        return r

    def action_toggle_is_locked(self):
        if self.aux_location_dest_id:
            return {
                    'warning': {
                        'title': _('Inventario'),
                        'message': _('No puede realizar esta acción')
                    }
                }
        return super(StockPicking, self).action_toggle_is_locked()

    def unlink(self):
        for line in self:
            if line.aux_location_dest_id:
                user_location_ids = ([x.id for x in line.env.user.location_ids if x])
                if not (line.location_id.id in user_location_ids):
                    msm = u"No tiene permisos para eliminar"
                    return {
                            'warning': {
                            'title': _('Inventario'),
                            'message': _(msm)
                        }
                    }
        return super(StockPicking, self).unlink()

    def copy(self, default=None):
        self.ensure_one()
        for line in self:
            if line.aux_location_dest_id:
                user_location_ids = ([x.id for x in line.env.user.location_ids if x])
                if not (line.location_id.id in user_location_ids):
                    msm = u"No tiene permisos para duplicar"
                    return {
                            'warning': {
                            'title': _('Inventario'),
                            'message': _(msm)
                        }
                    }
        return super(StockPicking, self).copy(default)


    @api.depends('state', 'is_locked')
    def _compute_show_validate(self):
        for picking in self:
            if picking.aux_location_dest_id:
                if picking.state == 'assigned':
                    picking.show_validate = True
            else:
                super(StockPicking, picking)._compute_show_validate()

    """
    @api.depends('location_dest_id')
    def _compute_can_validate(self):
        if self.aux_location_dest_id:
            if self.location_dest_id.id in self.env.user.location_ids.ids:
                self.can_validate = True
            else:
                self.can_validate = False

    """

    @api.onchange('aux_location_dest_id')
    def onchange_aux_location_dest_id(self):
        if self.aux_location_dest_id:
            self.show_validate = False
            warehouse_id = self.env['stock.warehouse'].search([
                ('view_location_id', '=', self.aux_location_dest_id.location_id.id)
            ])
            self.location_dest_id = self.aux_location_dest_id
            if len(warehouse_id):
                picking_type_id = self.picking_type_id.search([
                    ('code', '=', 'internal'), ('active', '=', True), ('warehouse_id', '=', warehouse_id.id)
                ])
                if len(picking_type_id) == 1:
                    self.picking_type_id = picking_type_id
            if self.move_line_ids:
                for lines in self.move_line_ids:
                    if lines.location_dest_id.id != self.location_dest_id.id:
                        lines.location_dest_id = self.aux_location_dest_id
            return {'domain': {'location_id': [('usage', '=', 'internal')]}}

    @api.onchange('location_id')
    def onchange_location_id(self):
        if self.aux_location_dest_id and self.move_line_ids:
                for lines in self.move_line_ids:
                    if lines.location_id.id != self.location_id.id:
                        lines.location_id = self.location_id

    @api.onchange('picking_type_id', 'partner_id')
    def onchange_picking_type(self):
        if not self.aux_location_dest_id:
            r = super(StockPicking, self).onchange_picking_type()
            return r

    def transfer(self):
        if self.aux_location_dest_id:
            if self.picking_type_id.show_reserved:
                location = [x.location_id.display_name for x in self.move_line_ids
                            if x.location_id.id != self.location_id.id]
                dest = [x.location_dest_id.display_name for x in self.move_line_ids
                        if x.location_dest_id.id != self.location_dest_id.id]
                if location:
                    msm = u"Las ubicación de origen [{}] es ​​diferentes a la ubicación de origen ({}) del item"
                    return {
                        'warning': {
                            'title': _('Inventario'),
                            'message': _(msm.format(', '.join(location), self.location_id.display_name))
                        }
                    }
                    
                if dest:
                    msm = u"La ubicaciones destino [{}] es diferente a la ubicacione de destino ({}) del item."
                    return {
                            'warning': {
                            'title': _('Inventario'),
                            'message': _(msm.format(', '.join(dest), self.location_dest_id.display_name))
                        }
                    }                    
                user_location_ids = ([x.id for x in self.env.user.location_ids if x])
                if not (self.location_id.id in user_location_ids):
                    msm = u"No tiene permisos para transferir desde 'Ubicación origen' {}"
                    return {
                            'warning': {
                            'title': _('Inventario'),
                            'message': _(msm.format(self.location_id.name))
                        }
                    }                    
            for line in self.move_line_ids:
                product_name = line.product_id.display_name
                if not line.product_id.type == 'product':
                    return {
                            'warning': {
                            'title': _('Inventario'),
                            'message': _(u"El producto {} debe ser de tipo Almacenable.".format(product_name))
                        }
                    }                     
                if self.location_id.id:
                    obj_sq = self.env['stock.quant'].search([
                                                            ('location_id', '=', self.location_id.id),
                                                            ('product_id', '=', line.product_id.id)
                                                            ])
                    product_stock_qty = sum([x.quantity for x in obj_sq if x.quantity])
                    product_qty = line.qty_done
                    name_warehouse = self.location_id.name
                    if product_qty > product_stock_qty:
                        if product_qty <= 0:
                            msm = "No puede transferir el producto {} con cantidad menor o igual a 0"
                            return {
                                    'warning': {
                                    'title': _('Inventario'),
                                    'message': _(msm.format(line.product_id.name))
                                }
                            }                             
                        else:
                            msm = u"Usted planea transferir {} {} pero solo tiene {} en {}"
                            messaje = msm.format(product_qty, product_name, product_stock_qty, name_warehouse)

                            return {
                                    'warning': {
                                    'title': _('Inventario'),
                                    'message': _(messaje)
                                }
                            }                            
            self.state = "assigned"
            self.is_locked = not self.is_locked
