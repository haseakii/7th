from deploy.config import DeployConfig as _DeployConfig


class DeployConfig(_DeployConfig):
    """WebUI 配置包装器。

    将属性写入持久化到 deploy.yaml。所有大写属性自动持久化。
    """

    def __setattr__(self, key: str, value):
        """写入属性时自动持久化到 deploy.yaml。"""
        super().__setattr__(key, value)
        if key[0].isupper():
            self._persist()

    def _persist(self):
        """将当前配置写回 deploy.yaml。"""
        try:
            import yaml
            with open(self._path, 'w', encoding='utf-8') as f:
                data = {k: self._data[k] for k in self._CONFIG_KEYS
                        if k in self._data and self._data[k] != self._DEFAULTS.get(k)}
                yaml.safe_dump(data, f, default_flow_style=False, allow_unicode=True)
        except Exception:
            pass
