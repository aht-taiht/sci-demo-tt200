import copy


def get_format_workbook(workbook):
    header_format = {
        'bold': 1,
        'border': 1,
        'size': 11,
        'font_color': '#FFFF',
        'align': 'center',
        'valign': 'vcenter',
        'text_wrap': True,
    }
    title_format = {
        'bold': 1,
        'border': 1,
        'align': 'center',
        'valign': 'vcenter',
        'text_wrap': True,
    }
    subtotal_format = {
        'bold': 1,
        'border': 1,
        'align': 'right',
        'valign': 'vcenter',
        'bg_color': '#004EAB',
        'font_color': '#FFFF',
    }
    normal_format = {
        'border': 1,
        'align': 'center',
        'valign': 'vcenter',
    }
    normal_info_format = {
        'align': 'left',
        'valign': 'vcenter',
    }
    note_format = {
        'align': 'left',
        'valign': 'vcenter'
    }
    bold_note_format = {
        'align': 'left',
        'valign': 'vcenter',
        'bold': 1
    }
    underline_note_format = {
        'align': 'left',
        'valign': 'vcenter',
        'bold': 1,
        'underline': True
    }
    align_left = {'align': 'left'}
    align_right = {'align': 'right'}
    align_center = {'align': 'center'}
    float_number_format = {}
    int_number_format = {}

    float_number_format.update(normal_format)
    int_number_format.update(normal_format)
    int_number_format.update(align_right)
    float_number_title_format = float_number_format.copy()
    float_number_title_format.update(title_format)
    int_number_title_format = int_number_format.copy()
    int_number_title_format.update(title_format)

    title_format = workbook.add_format(title_format)
    normal_format = workbook.add_format(normal_format)
    normal_info_format = workbook.add_format(normal_info_format)

    float_number_format = workbook.add_format(float_number_format)
    float_number_format.set_num_format('#,##0.00')
    int_number_format = workbook.add_format(int_number_format)
    int_number_format.set_num_format('#,##0')
    int_subtotal_format = workbook.add_format(subtotal_format)
    int_subtotal_format.set_num_format('#,##0')
    int_subtotal_format.set_align('right')
    subtotal_format = workbook.add_format(subtotal_format)

    float_number_title_format = workbook.add_format(float_number_title_format)
    float_number_title_format.set_num_format('#,##0.00')
    int_number_title_format = workbook.add_format(int_number_title_format)
    int_number_title_format.set_num_format('#,##0')

    clone_header_format = copy.copy(header_format)
    clone_header_format.update({'bg_color': '#004EAB', **align_center})
    main_header_format = workbook.add_format(clone_header_format)
    clone_header_format.update({'bg_color': '#FF3366'})
    sub_header_format = workbook.add_format(clone_header_format)

    clone_header_format.update({'bg_color': '#FF3366', 'underline': True, **align_left})
    info_header_format = workbook.add_format(clone_header_format)

    clone_header_format.update({'bg_color': '#004EAB', 'underline': False})
    info_content_format = workbook.add_format(clone_header_format)

    note_format = workbook.add_format(note_format)
    bold_note_format = workbook.add_format(bold_note_format)
    underline_note_format = workbook.add_format(underline_note_format)
    values = {
        'info_header_format': info_header_format,
        'info_content_format': info_content_format,
        'main_header_format': main_header_format,
        'sub_header_format': sub_header_format,
        'title_format': title_format,
        'normal_info_format': normal_info_format,
        'normal_format': normal_format,
        'float_number_format': float_number_format,
        'int_number_format': int_number_format,
        'float_number_title_format': float_number_title_format,
        'int_number_title_format': int_number_title_format,
        'subtotal_format': subtotal_format,
        'int_subtotal_format': int_subtotal_format,
        'note_format': note_format,
        'bold_note_format': bold_note_format,
        'underline_note_format': underline_note_format
    }
    return values


def get_wood_format_workbook(env, workbook):
    report_title_format = {
        'bold': 1,
        'align': 'center',
        'valign': 'vcenter',
        'text_wrap': True,
        'font_size': 14,
        'bg_color': env.company.header_color_code or '#004EAB',
        'font_color': '#FFFFF'
    }
    title_format = {
        'bold': 1,
        'border': 1,
        'align': 'center',
        'valign': 'vcenter',
        'text_wrap': True,
        'font_size': 14
    }
    header_table_format = {
        'bold': 1,
        'border': 1,
        'align': 'center',
        'valign': 'vcenter',
        'text_wrap': True,
        'bg_color': '#E6E7E8',
        'font_size': 14,
    }
    title_info_format = {
        'bold': 1,
        'align': 'left',
        'valign': 'vcenter',
        'text_wrap': True,
        'font_size': 14,
    }
    subtotal_format = {
        'bold': 1,
        'border': 1,
        'align': 'right',
        'valign': 'vcenter',
        'bg_color': '#E6E7E8',
        'font_size': 14,
    }
    normal_format = {
        'border': 1,
        'align': 'center',
        'valign': 'vcenter',
        'font_size': 14,
    }
    normal_info_format = {
        'align': 'left',
        'valign': 'vcenter',
        'font_size': 14,
    }
    note_format = {
        'align': 'left',
        'valign': 'vcenter',
        'font_size': 14,
    }
    bold_note_format = {
        'align': 'left',
        'valign': 'vcenter',
        'bold': 1,
        'font_size': 14,
    }
    underline_note_format = {
        'align': 'left',
        'valign': 'vcenter',
        'bold': 1,
        'underline': True,
        'font_size': 14,
    }
    italic_format = {
        'align': 'left',
        'valign': 'vcenter',
        'italic': True,
        'font_size': 14,
    }
    align_left = {'align': 'left'}
    align_right = {'align': 'right'}
    align_center = {'align': 'center'}
    float_number_format = {}

    float_number_format.update(normal_format)
    float_number_title_format = float_number_format.copy()
    float_number_title_format.update(title_format)

    report_title_format = workbook.add_format(report_title_format)
    title_format = workbook.add_format(title_format)
    normal_format = workbook.add_format(normal_format)
    italic_format = workbook.add_format(italic_format)

    title_info_format = workbook.add_format(title_info_format)
    normal_info_format = workbook.add_format(normal_info_format)

    float_number_subtotal_format = copy.copy(float_number_format)

    float_number_format = workbook.add_format(float_number_format)
    float_number_format.set_num_format('#,##0.00')

    float_number_subtotal_format = copy.copy(float_number_subtotal_format)
    float_number_subtotal_format.update({'bg_color': '#E6E7E8'})
    float_number_subtotal_format = workbook.add_format(float_number_subtotal_format)
    float_number_subtotal_format.set_num_format('#,##0.00')

    subtotal_format = workbook.add_format(subtotal_format)

    float_number_title_format = workbook.add_format(float_number_title_format)
    float_number_title_format.set_num_format('#,##0.00')

    header_table_format = workbook.add_format(header_table_format)

    note_format = workbook.add_format(note_format)
    bold_note_format = workbook.add_format(bold_note_format)
    underline_note_format = workbook.add_format(underline_note_format)
    values = {
        'report_title_format': report_title_format,
        'header_table_format': header_table_format,
        'title_info_format': title_info_format,
        'normal_info_format': normal_info_format,
        'title_format': title_format,
        'normal_format': normal_format,
        'float_number_format': float_number_format,
        'subtotal_format': subtotal_format,
        'float_number_subtotal_format': float_number_subtotal_format,
        'note_format': note_format,
        'bold_note_format': bold_note_format,
        'underline_note_format': underline_note_format,
        'italic_format': italic_format
    }
    return values
