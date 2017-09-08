from json import loads
from os import path, remove, listdir

from PySide.QtGui import QMessageBox

from .Downloading import download
from ._paths import CACHESPATH

CHECKED = False


def is_YTDL_importable():
    try:
        from .youtube_dl import version
        return True
    except ImportError:
        return False


def updateYTD(noCheck=False, showMessage=True, useYield=False):
    """
    With info from https://stackoverflow.com/a/26454035
    """
    from .youtube_dl import version
    try:
        global CHECKED
        if CHECKED:
            return
        CHECKED = True
        data = download('https://api.github.com/repos/rg3/youtube-dl/releases/latest')
        parsedData = loads(data.decode('utf-8'))

        remoteVersion = parsedData['tag_name']
        localVersion = version.__version__
        isNewVersion = remoteVersion > localVersion
        if useYield:
            yield isNewVersion

        if noCheck or isNewVersion:
            if noCheck:
                reason = 'missing'
            else:
                reason = 'outdated'

            if showMessage:
                QMessageBox.warning(None, 'Tool {}'.format(reason), 'Youtube-DL is {}.\n'.format(reason)
                                    + 'New version ({}) will be downloaded now.'.format(remoteVersion),
                                    QMessageBox.Ok)

            package = download(parsedData['tarball_url'])
            _packageTar = path.join(CACHESPATH, '_temp_ytd.tar')
            with open(_packageTar, 'xb') as file:
                file.write(package)

            from shutil import unpack_archive, rmtree, move

            parentDir = path.dirname(__file__)
            packagePath = path.join(parentDir, 'youtube_dl')
            if path.exists(packagePath):
                rmtree(packagePath)
            destPath = path.join(parentDir, '_newpackage_')
            unpack_archive(_packageTar, destPath, 'gztar')
            remove(_packageTar)
            for d in listdir(destPath):
                currDir = path.join(destPath, d)
                if path.isdir(currDir) and d.startswith('rg3-youtube-dl'):
                    move(path.join(currDir, 'youtube_dl'), packagePath)
                    move(path.join(currDir, 'LICENSE'), path.join(packagePath, 'LICENSE'))
                    rmtree(destPath)
                    break

            if useYield:
                yield

    except Exception as err:
        print('YTD check error', err)
        if useYield:
            yield 
