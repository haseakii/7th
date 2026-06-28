import os
import sys
from unittest.mock import MagicMock, patch

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from alas import E7AutoScript
from module.config.config import TaskEnd
from module.device.device import DeviceController
from module.exception import RequestHumanTakeover, ScriptError
from module.task.registry import TaskSpec, get_task, list_tasks
from module.vision.frame import FrameContext, capture_device_frame
from module.vision.profile import SECRET_SHOP_PROFILE
from tasks.secret_shop.navigator import (
    CONTENT_BRIGHTNESS_THRESHOLD,
    LOBBY_NAV_MIN_BRIGHTNESS,
    SECRET_SHOP_SIDEBAR_THRESHOLD,
)
from tasks.secret_shop.ocr_engine import OCR


def test_secret_shop_is_registered():
    spec = get_task("SecretShop")
    assert spec is not None
    assert spec.method == "secret_shop"
    assert spec in list_tasks()


def test_scheduler_run_uses_registered_task():
    fake_task = MagicMock()
    fake_spec = TaskSpec(
        command="FakeTask",
        method="fake_task",
        factory=MagicMock(return_value=fake_task),
    )
    scheduler = E7AutoScript(config=MagicMock())
    scheduler._device = MagicMock()

    with patch("alas.get_task", return_value=fake_spec):
        assert scheduler.run("FakeTask") is True

    fake_spec.factory.assert_called_once_with(
        config=scheduler.config,
        device=scheduler.device,
        task="FakeTask",
    )
    fake_task.run.assert_called_once()


def test_scheduler_can_construct_registered_secret_shop_task():
    scheduler = E7AutoScript(config=MagicMock())
    scheduler._device = MagicMock()

    with patch("shop_bot.ShopBot.run_loop") as run_loop:
        assert scheduler.run("SecretShop") is True

    run_loop.assert_called_once()


def test_process_manager_runs_registered_task_directly():
    from module.webui.process_manager import ProcessManager

    queue = MagicMock()

    with patch("module.webui.process_manager.set_file_logger"), \
         patch("module.webui.process_manager.set_func_logger"), \
         patch("module.webui.process_manager.remove_fake_pil_module"), \
         patch("alas.E7AutoScript") as MockScript:
        instance = MockScript.return_value
        instance.init.return_value = True

        ProcessManager.run_process("default", "SecretShop", queue, None)

    instance.loop.assert_not_called()
    instance.run.assert_called_once_with("SecretShop")


def test_scheduler_fallback_task_end_is_success():
    scheduler = E7AutoScript(config=MagicMock())

    def legacy_task():
        raise TaskEnd()

    scheduler.legacy_task = legacy_task
    with patch("alas.get_task", return_value=None):
        assert scheduler.run("legacy_task") is True


def test_scheduler_unknown_task_raises_script_error():
    scheduler = E7AutoScript(config=MagicMock())

    with patch("alas.get_task", return_value=None):
        try:
            scheduler.run("MissingTask")
        except ScriptError as exc:
            assert "MissingTask" in str(exc)
        else:
            raise AssertionError("Expected ScriptError")


def test_scheduler_waits_when_all_tasks_are_disabled():
    config = MagicMock()
    config.get_next.side_effect = RequestHumanTakeover
    scheduler = E7AutoScript(config=config)
    scheduler._stop_event = MagicMock()
    scheduler._stop_event.is_set.return_value = False
    scheduler._stop_event.wait.side_effect = [False, True]

    scheduler.loop()

    assert config.load.call_count == 2
    assert scheduler._stop_event.wait.call_args_list[0].args == (10,)


def test_frame_context_ocr_cache_is_per_frame():
    image = np.zeros((20, 20, 3), dtype=np.uint8)
    frame = FrameContext(image=image)
    backend = MagicMock()
    backend.predict.return_value = []

    with patch.object(OCR, "_ensure_backend", return_value=backend):
        assert OCR.read(frame, region=(0, 0, 10, 10), min_confidence=0.4) == []
        assert OCR.read(frame, region=(0, 0, 10, 10), min_confidence=0.4) == []
        assert backend.predict.call_count == 1

        other_frame = FrameContext(image=image)
        assert OCR.read(other_frame, region=(0, 0, 10, 10), min_confidence=0.4) == []
        assert backend.predict.call_count == 2


def test_device_capture_frame_handles_missing_screenshot():
    device = DeviceController.__new__(DeviceController)
    device.screenshot = MagicMock(return_value=None)

    assert device.capture_frame() is None


def test_capture_device_frame_wraps_legacy_device():
    image = np.zeros((20, 20, 3), dtype=np.uint8)
    device = MagicMock()
    device.screenshot.return_value = image

    frame = capture_device_frame(device)

    assert isinstance(frame, FrameContext)
    assert frame.image is image


def test_secret_shop_profile_exports_existing_thresholds():
    assert SECRET_SHOP_SIDEBAR_THRESHOLD == SECRET_SHOP_PROFILE.secret_shop_sidebar_threshold
    assert LOBBY_NAV_MIN_BRIGHTNESS == SECRET_SHOP_PROFILE.lobby_nav_min_brightness
    assert CONTENT_BRIGHTNESS_THRESHOLD == SECRET_SHOP_PROFILE.content_brightness_threshold
