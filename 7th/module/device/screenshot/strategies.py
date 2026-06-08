"""
截图策略具体实现 — 含 ALAS 完整底层方法
"""

import os
import subprocess
import time

import cv2
import numpy as np
import requests

from module.logger import logger
from module.device.adb_utils import ADB_EXECUTABLE, adb_shell, adb_shell_stream, adb_push, adb_forward
from module.device.alas_paths import ASCREENCAP_DIR, DROIDCAST_APK
from module.device.screenshot.base import ScreenshotStrategy
from module.device.screenshot import register

# 兼容别名
_ASCREENCAP_BIN = ASCREENCAP_DIR
_DROIDCAST_JAR = DROIDCAST_APK


# ============================================================================
# 基础策略
# ============================================================================

@register("adb")
class AdbScreenshot(ScreenshotStrategy):
    """ADB screencap -p（PNG 编码），兼容所有设备。"""

    def __init__(self, serial: str):
        self.serial = serial

    def initialize(self) -> bool:
        return True

    @property
    def name(self) -> str:
        return "adb"

    def screenshot(self) -> np.ndarray:
        result = subprocess.run(
            [ADB_EXECUTABLE, "-s", self.serial, "exec-out", "screencap", "-p"],
            capture_output=True, timeout=15
        )
        if result.returncode != 0:
            raise RuntimeError(f"ADB 截图失败: {result.stderr.decode(errors='ignore')[:200]}")
        nparr = np.frombuffer(result.stdout, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if image is None:
            raise RuntimeError("ADB 截图解码失败")
        return image


@register("adb_nc")
class AdbNcScreenshot(ScreenshotStrategy):
    """ADB 无压缩截图（adb_raw 别名），跳过 PNG 编解码。"""

    TARGET_WIDTH = 1280
    TARGET_HEIGHT = 720

    def __init__(self, serial: str):
        self.serial = serial

    def initialize(self) -> bool:
        return True

    @property
    def name(self) -> str:
        return "adb_nc"

    def screenshot(self) -> np.ndarray:
        data = adb_shell_stream(self.serial, ["screencap"], timeout=15)
        pixels = np.frombuffer(data[12:], dtype=np.uint8)
        try:
            img = pixels.reshape(self.TARGET_HEIGHT, self.TARGET_WIDTH, 4)
            img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)
        except ValueError:
            img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
            if img is None:
                raise RuntimeError("ADB nc 截图回退解码失败")
        return img


@register("uiautomator2")
class U2Screenshot(ScreenshotStrategy):
    """uiautomator2 截图。需要设备端 u2 server。"""

    def __init__(self, serial: str):
        self.serial = serial
        self._u2 = None

    def initialize(self) -> bool:
        import uiautomator2 as u2
        self._u2 = u2.connect(self.serial)
        if self._u2 is None:
            raise RuntimeError("uiautomator2 连接返回 None")
        logger.info(f"uiautomator2 连接成功: {self.serial}")
        return True

    @property
    def name(self) -> str:
        return "uiautomator2"

    def screenshot(self) -> np.ndarray:
        if self._u2 is None:
            raise RuntimeError("uiautomator2 未初始化")
        pil_img = self._u2.screenshot()
        img = np.array(pil_img)
        img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        return img


# ============================================================================
# aScreenCap — C 程序快速截图（lz4 压缩）
# ============================================================================

@register("ascreencap")
class AScreenCapScreenshot(ScreenshotStrategy):
    """aScreenCap — C 编写的快速截图工具。

    ALAS 方案：将预编译的 ascreencap 二进制推送到设备，
    通过 ADB shell 执行，输出 lz4 压缩的流数据，
    在 PC 端解压为 BGR 图像。
    比 ADB screencap -p 快 3-5x。
    """

    REMOTE_PATH = "/data/local/tmp/ascreencap"

    def __init__(self, serial: str):
        self.serial = serial
        self._initialized = False
        self._available = True
        self._binary_path = None

    def initialize(self) -> bool:
        if not self._available:
            return False
        try:
            # 检测设备 CPU 架构和 SDK 版本
            abi = adb_shell(self.serial, ["getprop", "ro.product.cpu.abi"]).decode().strip()
            sdk_str = adb_shell(self.serial, ["getprop", "ro.build.version.sdk"]).decode().strip()
            sdk = int(sdk_str) if sdk_str else 0

            # 匹配 Android 版本目录
            if 21 <= sdk <= 25:
                ver_dir = "Android_5.x-7.x"
            elif 26 <= sdk <= 27:
                ver_dir = "Android_8.x"
            elif sdk == 28:
                ver_dir = "Android_9.x"
            else:
                ver_dir = "Android_9.x"  # 用最新的试试

            # 匹配 CPU 架构
            arch_map = {
                'arm64-v8a': 'arm64-v8a',
                'armeabi-v7a': 'armeabi-v7a',
                'x86_64': 'x86_64',
                'x86': 'x86',
            }
            arch = arch_map.get(abi, 'arm64-v8a')
            self._binary_path = os.path.join(_ASCREENCAP_BIN, ver_dir, arch, 'ascreencap')

            if not os.path.isfile(self._binary_path):
                logger.warning(f"aScreenCap 二进制不存在: {self._binary_path}")
                self._available = False
                return False

            adb_push(self.serial, self._binary_path, self.REMOTE_PATH)
            adb_shell(self.serial, ["chmod", "0777", self.REMOTE_PATH])
            self._initialized = True
            logger.info(f"aScreenCap 初始化完成 ({ver_dir}/{abi})")
            return True
        except Exception as e:
            logger.warning(f"aScreenCap 初始化失败: {e}")
            self._available = False
            return False

    @property
    def name(self) -> str:
        return "ascreencap"

    def screenshot(self) -> np.ndarray:
        if not self._initialized:
            raise RuntimeError("aScreenCap 未初始化")
        data = adb_shell_stream(self.serial, [self.REMOTE_PATH, "--pack", "2", "--stdout"])
        return self._decompress(data)

    @staticmethod
    def _decompress(data: bytes) -> np.ndarray:
        """lz4 解压 + 解析为 BGR 图像。"""
        from lz4.block import decompress as lz4_decompress

        # 跳过 ADB 输出的 linker 警告等前缀，定位到 BMZ1 头部
        header_pos = data.find(b'BMZ1')
        if header_pos < 0:
            raise RuntimeError("aScreenCap: 未找到 BMZ1 头部")
        raw = data[header_pos:]

        # 解析 20 字节头部
        header = np.frombuffer(raw[0:20], dtype=np.uint32)
        if header[0] != 828001602:
            header = header.byteswap()
            if header[0] != 828001602:
                raise RuntimeError("aScreenCap: 头部校验失败")

        _, uncompressed_size, _, width, height = header
        channel = 3

        # lz4 解压
        decompressed = lz4_decompress(raw[20:], uncompressed_size=uncompressed_size)
        image = np.frombuffer(decompressed, dtype=np.uint8)

        # reshape、翻转、BGR 转换
        try:
            image = image[-int(width * height * channel):].reshape(height, width, channel)
        except ValueError as e:
            raise RuntimeError(f"aScreenCap: reshape 失败 ({e})")

        image = cv2.flip(image, 0)
        cv2.cvtColor(image, cv2.COLOR_BGR2RGB, dst=image)
        return image


@register("ascreencap_nc")
class AScreenCapNcScreenshot(ScreenshotStrategy):
    """aScreenCap 无压缩截图（通过 nc 传回）。"""

    REMOTE_PATH = AScreenCapScreenshot.REMOTE_PATH

    def __init__(self, serial: str):
        self.serial = serial
        self._initialized = False
        self._available = True

    def initialize(self) -> bool:
        if not self._available:
            return False
        try:
            # 同 ascreencap 的架构检测逻辑
            abi = adb_shell(self.serial, ["getprop", "ro.product.cpu.abi"]).decode().strip()
            sdk_str = adb_shell(self.serial, ["getprop", "ro.build.version.sdk"]).decode().strip()
            sdk = int(sdk_str) if sdk_str else 0

            if 21 <= sdk <= 25:
                ver_dir = "Android_5.x-7.x"
            elif 26 <= sdk <= 27:
                ver_dir = "Android_8.x"
            elif sdk == 28:
                ver_dir = "Android_9.x"
            else:
                ver_dir = "Android_9.x"

            arch_map = {'arm64-v8a': 'arm64-v8a', 'armeabi-v7a': 'armeabi-v7a', 'x86_64': 'x86_64', 'x86': 'x86'}
            arch = arch_map.get(abi, 'arm64-v8a')
            binary_path = os.path.join(_ASCREENCAP_BIN, ver_dir, arch, 'ascreencap')

            if not os.path.isfile(binary_path):
                logger.warning(f"aScreenCap 二进制不存在: {binary_path}")
                self._available = False
                return False

            adb_push(self.serial, binary_path, self.REMOTE_PATH)
            adb_shell(self.serial, ["chmod", "0777", self.REMOTE_PATH])
            self._initialized = True
            logger.info(f"aScreenCap (nc) 初始化完成 ({ver_dir}/{abi})")
            return True
        except Exception as e:
            logger.warning(f"aScreenCap (nc) 初始化失败: {e}")
            self._available = False
            return False

    @property
    def name(self) -> str:
        return "ascreencap_nc"

    def screenshot(self) -> np.ndarray:
        if not self._initialized:
            raise RuntimeError("aScreenCap (nc) 未初始化")
        data = adb_shell_stream(self.serial, [self.REMOTE_PATH, "--pack", "2", "--stdout"])
        # 同 ascreencap，但跳过位置修复逻辑
        return AScreenCapScreenshot._decompress(data)


# ============================================================================
# DroidCast — Java 截图服务器（HTTP）
# ============================================================================

@register("droidcast")
class DroidCastScreenshot(ScreenshotStrategy):
    """DroidCast — 推送到设备后台运行，通过 HTTP 获取 PNG 截图。"""

    REMOTE_PATH = "/data/local/tmp/DroidCast_raw.apk"
    REMOTE_PORT = 53516

    def __init__(self, serial: str):
        self.serial = serial
        self._local_port = 0
        self._initialized = False
        self._session = None

    def initialize(self) -> bool:
        if not os.path.isfile(_DROIDCAST_JAR):
            logger.warning(f"DroidCast APK 不存在: {_DROIDCAST_JAR}")
            return False

        try:
            # 推送 APK
            adb_push(self.serial, _DROIDCAST_JAR, self.REMOTE_PATH)

            # 启动 DroidCast 后台进程
            # CLASSPATH=/data/local/tmp/DroidCast_raw.apk app_process / ink.mol.droidcast_raw.Main
            subprocess.run(
                [ADB_EXECUTABLE, "-s", self.serial, "shell",
                 f"CLASSPATH={self.REMOTE_PATH}",
                 "app_process", "/", "ink.mol.droidcast_raw.Main", ">", "/dev/null", "&"],
                capture_output=True, timeout=10
            )

            # 端口转发
            self._local_port = adb_forward(
                self.serial, f"tcp:{self.REMOTE_PORT}", f"tcp:{self.REMOTE_PORT}"
            )

            # HTTP session
            self._session = requests.Session()
            self._session.trust_env = False

            # 等待启动
            if not self._wait_startup():
                logger.warning("DroidCast 启动超时")
                return False

            self._initialized = True
            logger.info(f"DroidCast 就绪 @127.0.0.1:{self._local_port}")
            return True
        except Exception as e:
            logger.warning(f"DroidCast 初始化失败: {e}")
            return False

    def _wait_startup(self, timeout: float = 10) -> bool:
        """等待 DroidCast 服务启动。返回是否成功。"""
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                resp = self._session.get(
                    f"http://127.0.0.1:{self._local_port}/",
                    timeout=3
                )
                if resp.status_code == 404:
                    return True
            except (requests.exceptions.ConnectionError, requests.exceptions.ReadTimeout):
                pass
            time.sleep(0.25)
        return False

    @property
    def name(self) -> str:
        return "droidcast"

    def screenshot(self) -> np.ndarray:
        if not self._initialized:
            raise RuntimeError("DroidCast 未初始化")
        resp = self._session.get(
            f"http://127.0.0.1:{self._local_port}/preview",
            timeout=10
        )
        if resp.status_code != 200:
            raise RuntimeError(f"DroidCast HTTP {resp.status_code}")

        image = np.frombuffer(resp.content, np.uint8)
        image = cv2.imdecode(image, cv2.IMREAD_COLOR)
        if image is None:
            raise RuntimeError("DroidCast 截图解码失败")

        cv2.cvtColor(image, cv2.COLOR_BGR2RGB, dst=image)
        return image


@register("droidcast_raw")
class DroidCastRawScreenshot(ScreenshotStrategy):
    """DroidCast_raw — RGB565 原始位图截图（比 PNG 版更快）。"""

    REMOTE_PATH = DroidCastScreenshot.REMOTE_PATH
    REMOTE_PORT = 53516

    def __init__(self, serial: str):
        self.serial = serial
        self._local_port = 0
        self._initialized = False
        self._session = None

    def initialize(self) -> bool:
        if not os.path.isfile(_DROIDCAST_JAR):
            logger.warning(f"DroidCast APK 不存在: {_DROIDCAST_JAR}")
            return False

        try:
            adb_push(self.serial, _DROIDCAST_JAR, self.REMOTE_PATH)
            subprocess.run(
                [ADB_EXECUTABLE, "-s", self.serial, "shell",
                 f"CLASSPATH={self.REMOTE_PATH}",
                 "app_process", "/", "ink.mol.droidcast_raw.Main", ">", "/dev/null", "&"],
                capture_output=True, timeout=10
            )
            self._local_port = adb_forward(
                self.serial, f"tcp:{self.REMOTE_PORT}", f"tcp:{self.REMOTE_PORT}"
            )
            self._session = requests.Session()
            self._session.trust_env = False

            # 等待启动
            if not self._droidcast_wait_startup():
                logger.warning("DroidCast_raw 启动超时")
                return False

            self._initialized = True
            logger.info(f"DroidCast_raw 就绪 @127.0.0.1:{self._local_port}")
            return True
        except Exception as e:
            logger.warning(f"DroidCast_raw 初始化失败: {e}")
            return False

    def _droidcast_wait_startup(self, timeout: float = 10) -> bool:
        """等待 DroidCast_raw 服务启动。"""
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                resp = self._session.get(
                    f"http://127.0.0.1:{self._local_port}/",
                    timeout=3
                )
                if resp.status_code == 404:
                    return True
            except (requests.exceptions.ConnectionError, requests.exceptions.ReadTimeout):
                pass
            time.sleep(0.25)
        return False

    @property
    def name(self) -> str:
        return "droidcast_raw"

    def screenshot(self) -> np.ndarray:
        if not self._initialized:
            raise RuntimeError("DroidCast_raw 未初始化")
        resp = self._session.get(
            f"http://127.0.0.1:{self._local_port}/screenshot",
            timeout=10
        )
        # DroidCast_raw 返回 RGB565 uint16 数组
        arr = np.frombuffer(resp.content, dtype=np.uint16)
        shape = (720, 1280)

        try:
            arr = arr.reshape(shape)
        except ValueError:
            raise RuntimeError("DroidCast_raw: reshape 失败")

        # RGB565 → RGB888
        tmp = np.empty_like(arr)
        cv2.bitwise_and(arr, 0b1111100000000000, dst=tmp)
        r = cv2.convertScaleAbs(tmp, alpha=0.0040283203125)
        cv2.bitwise_and(arr, 0b0000011111100000, dst=tmp)
        g = cv2.convertScaleAbs(tmp, alpha=0.126953125)
        cv2.bitwise_and(arr, 0b0000000000011111, dst=tmp)
        b = cv2.convertScaleAbs(tmp, alpha=8.25)

        image = cv2.merge([r, g, b])
        return cv2.cvtColor(image, cv2.COLOR_RGB2BGR)


# ============================================================================
# nemu_ipc — MuMu 模拟器共享内存截图（仅 MuMu 12）
# ============================================================================

@register("nemu_ipc")
class NemuIpcScreenshot(ScreenshotStrategy):
    """MuMu IPC 共享内存截图 — 仅支持 MuMu 12 模拟器，速度最快（~5ms）。"""

    def __init__(self, serial: str):
        self.serial = serial
        self._available = False

    def initialize(self) -> bool:
        logger.info("nemu_ipc: 检查 MuMu 模拟器...")
        # 检查 MuMu 模拟器是否需要
        # 通过检查 ADB 连接的模拟器信息判断
        try:
            props = adb_shell(self.serial, ["getprop", "ro.product.manufacturer"])
            if b"MuMu" in props or b"Nemu" in props:
                logger.info("nemu_ipc: 检测到 MuMu 模拟器，但需要 MuMu SDK 支持")
            else:
                logger.info("nemu_ipc: 非 MuMu 模拟器，不可用")
            return False
        except Exception as e:
            logger.warning(f"nemu_ipc 检测异常: {e}")
            return False

    @property
    def name(self) -> str:
        return "nemu_ipc"

    def screenshot(self) -> np.ndarray:
        raise NotImplementedError("nemu_ipc 需要 MuMu SDK，待实现")


# ============================================================================
# ldopengl — LDPlayer OpenGL 截图（仅 LDPlayer）
# ============================================================================

@register("ldopengl")
class LdopenglScreenshot(ScreenshotStrategy):
    """LDPlayer OpenGL 截图 — 仅支持 LDPlayer 模拟器。"""

    def __init__(self, serial: str):
        self.serial = serial

    def initialize(self) -> bool:
        logger.info("ldopengl: 需要 LDPlayer 模拟器及对应 SDK")
        return False

    @property
    def name(self) -> str:
        return "ldopengl"

    def screenshot(self) -> np.ndarray:
        raise NotImplementedError("ldopengl 需要 LDPlayer SDK，待实现")
