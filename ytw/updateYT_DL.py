from json import loads
from os import path, remove, listdir

from PySide.QtGui import QMessageBox

from .Downloading import download
from ._paths import CACHESPATH


def is_YTDL_importable():
    try:
        from .youtube_dl import version
        return True
    except ImportError:
        return False


def updateYTD(noCheck=False):
    """
    With info from https://stackoverflow.com/a/26454035
    """
    try:
        data = download('https://api.github.com/repos/rg3/youtube-dl/releases/latest')
        parsedData = loads(data.decode('utf-8'))

        if noCheck or parsedData['tag_name'] > version.__version__:
            QMessageBox.warning(None, 'Tool outdated', 'Youtube-DL is outdated.\n'
                                                       'New version will be downloaded now.',
                                QMessageBox.Ok)

            package = download(parsedData['tarball_url'])
            _packageTar = path.join(CACHESPATH, '_temp_ytd.tar')
            with open(_packageTar, 'xb') as file:
                file.write(package)

            from shutil import unpack_archive, rmtree, move

            parentDir = path.dirname(__file__)
            destPath = path.join(parentDir, '_newpackage_')
            unpack_archive(_packageTar, destPath, 'gztar')
            remove(_packageTar)
            for d in listdir(destPath):
                currDir = path.join(destPath, d)
                if path.isdir(currDir) and d.startswith('rg3-youtube-dl'):
                    move(path.join(currDir, 'youtube_dl'), path.join(parentDir, 'youtube_dl'))
                    rmtree(destPath)
                    break

    except Exception as err:
        print('YTD check error', err)
        return