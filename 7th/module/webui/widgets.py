"""
Widgets — ALAS 风格配置表单控件

每个 put_arg_* 函数接收完整 kwargs 字典，返回 PyWebIO Output 对象。
由 put_output 根据 widget_type 分派到对应函数。
"""

from typing import Any, Dict, List

from pywebio.io_ctrl import Output
from pywebio.output import put_column, put_scope, put_text
from pywebio.pin import put_checkbox, put_input, put_select, put_textarea

T_Output_Kwargs = Dict[str, Any]


def get_title_help(kwargs: T_Output_Kwargs) -> Output:
    """渲染参数标题和帮助文本（ALAS 风格）。"""
    title = kwargs.get("title", "")
    help_text = kwargs.get("help")
    if help_text:
        return put_column(
            [
                put_text(title).style("--arg-title--"),
                put_text(help_text).style("--arg-help--"),
            ],
            size="auto 1fr",
        )
    return put_text(title).style("--arg-title--")


def put_arg_input(kwargs: T_Output_Kwargs) -> Output:
    """文本/数字输入框。"""
    name = kwargs["name"]
    clean = {
        "name": name,
        "label": "",
        "value": str(kwargs.get("value", "")),
    }
    return put_scope(
        f"arg_container-input-{name}",
        [get_title_help(kwargs), put_input(**clean).style("--input--")],
    )


def put_arg_select(kwargs: T_Output_Kwargs) -> Output:
    """下拉选择框。"""
    name = kwargs["name"]
    value = kwargs.get("value", "")
    options: List[str] = kwargs.get("options", [])
    options_label: List[str] = kwargs.pop("options_label", options)

    option_list = [
        {"label": lbl, "value": opt, "select": opt == value}
        for opt, lbl in zip(options, options_label)
    ]
    clean = {
        "name": name,
        "label": "",
        "options": option_list,
        "value": value,
    }
    return put_scope(
        f"arg_container-select-{name}",
        [get_title_help(kwargs), put_select(**clean).style("--input--")],
    )


def put_arg_checkbox(kwargs: T_Output_Kwargs) -> Output:
    """开关式复选框。"""
    name = kwargs["name"]
    value = kwargs.get("value", False)

    clean = {
        "name": name,
        "label": "",
        "options": [{"label": "", "value": True, "selected": value}],
    }
    return put_scope(
        f"arg_container-checkbox-{name}",
        [get_title_help(kwargs), put_checkbox(**clean).style("text-align: center")],
    )


def put_arg_textarea(kwargs: T_Output_Kwargs) -> Output:
    """多行文本输入。"""
    name = kwargs["name"]
    clean = {
        "name": name,
        "label": "",
        "value": str(kwargs.get("value", "")),
    }
    return put_scope(
        f"arg_container-textarea-{name}",
        [get_title_help(kwargs), put_textarea(**clean)],
    )


# widget_type -> rendering function dispatch table
_widget_type_to_func = {
    "input": put_arg_input,
    "select": put_arg_select,
    "checkbox": put_arg_checkbox,
    "textarea": put_arg_textarea,
}


def put_output(output_kwargs: T_Output_Kwargs) -> Output:
    """根据 widget_type 分派到对应渲染函数。"""
    return _widget_type_to_func[output_kwargs["widget_type"]](output_kwargs)
