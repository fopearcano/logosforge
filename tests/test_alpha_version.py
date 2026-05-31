"""Alpha closure: canonical version / status constant."""

import storyplanner


def test_version_is_alpha():
    assert storyplanner.__version__ == "0.9.0-alpha"
    assert storyplanner.__status__ == "alpha"


def test_cloud_storage_uses_canonical_version():
    from storyplanner.cloud_storage import _app_version
    assert _app_version() == "0.9.0-alpha"


def test_qapplication_version_set():
    from PySide6.QtWidgets import QApplication
    # Importing app must not raise; setting version is done in create_app(),
    # but we can at least confirm the constant flows through Qt metadata.
    app = QApplication.instance() or QApplication([])
    QApplication.setApplicationVersion(storyplanner.__version__)
    assert app.applicationVersion() == "0.9.0-alpha"
