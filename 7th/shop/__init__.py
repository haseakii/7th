"""
商店业务逻辑模块 - 已迁移至 tasks.secret_shop

⚠ 此目录仅保留向后兼容 shim，新代码请直接导入 tasks.secret_shop
"""
import warnings
warnings.warn(
    "shop/ 模块已迁移至 tasks/secret_shop/，请更新导入路径",
    DeprecationWarning, stacklevel=2
)
