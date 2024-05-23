# -*- coding: utf-8 -*-

from . import project_project
from . import account_move
from . import account_journal
from . import ir_sequence
from . import sale_order
from . import sale_order_line
from . import res_partner
from . import product_category
from . import purchase_order

from odoo.addons.sale_project.models.sale_order_line import SaleOrderLine


def _timesheet_service_generation_custom(self):
    """ For service lines, create the task or the project. If already exists, it simply links
        the existing one to the line.
        Note: If the SO was confirmed, cancelled, set to draft then confirmed, avoid creating a
        new project/task. This explains the searches on 'sale_line_id' on project/task. This also
        implied if so line of generated task has been modified, we may regenerate it.
    """
    so_line_task_global_project = self.filtered(
        lambda sol: sol.is_service and sol.product_id.service_tracking == 'task_global_project')
    so_line_new_project = self.filtered(
        lambda sol: sol.is_service and sol.product_id.service_tracking in ['project_only', 'task_in_project'])

    # search so lines from SO of current so lines having their project generated, in order to check if the current one can
    # create its own project, or reuse the one of its order.
    map_so_project = {}
    if so_line_new_project:
        order_ids = self.mapped('order_id').ids
        so_lines_with_project = self.search([('order_id', 'in', order_ids), ('project_id', '!=', False),
                                             ('product_id.service_tracking', 'in', ['project_only', 'task_in_project']),
                                             ('product_id.project_template_id', '=', False)])
        map_so_project = {sol.order_id.id: sol.project_id for sol in so_lines_with_project}
        so_lines_with_project_templates = self.search([('order_id', 'in', order_ids), ('project_id', '!=', False), (
            'product_id.service_tracking', 'in', ['project_only', 'task_in_project']),
            ('product_id.project_template_id', '!=', False)])
        map_so_project_templates = {(sol.order_id.id, sol.product_id.project_template_id.id): sol.project_id for sol in
                                    so_lines_with_project_templates}

    # search the global project of current SO lines, in which create their task
    map_sol_project = {}
    if so_line_task_global_project:
        map_sol_project = {sol.id: sol.product_id.with_company(sol.company_id).project_id for sol in
                           so_line_task_global_project}

    def _can_create_project(sol):
        if not sol.project_id:
            if sol.product_id.project_template_id:
                return (sol.order_id.id, sol.product_id.project_template_id.id) not in map_so_project_templates
            elif sol.order_id.id not in map_so_project:
                return True
        return False

    def _determine_project(so_line):
        """Determine the project for this sale order line.
        Rules are different based on the service_tracking:

        - 'project_only': the project_id can only come from the sale order line itself
        - 'task_in_project': the project_id comes from the sale order line only if no project_id was configured
          on the parent sale order"""

        # Find the project by the analytic account on Sale Order
        analytic_account_id = so_line.order_id.analytic_account_id
        if analytic_account_id:
            existed_project = self.env['project.project'].search(
                [('analytic_account_id', '=', analytic_account_id.id)], limit=1)
            if existed_project:
                if so_line.product_id.service_tracking == 'project_only' and not so_line.project_id:
                    so_line.project_id = existed_project
                elif so_line.product_id.service_tracking == 'task_in_project' and not so_line.order_id.project_id:
                    so_line.order_id.project_id = existed_project
                return existed_project

        if so_line.product_id.service_tracking == 'project_only':
            return so_line.project_id
        elif so_line.product_id.service_tracking == 'task_in_project':
            return so_line.order_id.project_id or so_line.project_id

        return False

    # task_global_project: create task in global project
    for so_line in so_line_task_global_project:
        if not so_line.task_id:
            if map_sol_project.get(so_line.id) and so_line.product_uom_qty > 0:
                so_line._timesheet_create_task(project=map_sol_project[so_line.id])

    # project_only, task_in_project: create a new project, based or not on a template (1 per SO). May be create a task too.
    # if 'task_in_project' and project_id configured on SO, use that one instead
    for so_line in so_line_new_project:
        project = _determine_project(so_line)
        if not project and _can_create_project(so_line):
            project = so_line._timesheet_create_project()
            if so_line.product_id.project_template_id:
                map_so_project_templates[(so_line.order_id.id, so_line.product_id.project_template_id.id)] = project
            else:
                map_so_project[so_line.order_id.id] = project
        elif not project:
            # Attach subsequent SO lines to the created project
            so_line.project_id = (
                map_so_project_templates.get((so_line.order_id.id, so_line.product_id.project_template_id.id))
                or map_so_project.get(so_line.order_id.id)
            )
        if so_line.product_id.service_tracking == 'task_in_project':
            if not project:
                if so_line.product_id.project_template_id:
                    project = map_so_project_templates[(so_line.order_id.id, so_line.product_id.project_template_id.id)]
                else:
                    project = map_so_project[so_line.order_id.id]
            if not so_line.task_id:
                so_line._timesheet_create_task(project=project)
        so_line._generate_milestone()


# Patching the Odoo base method
SaleOrderLine._timesheet_service_generation = _timesheet_service_generation_custom
