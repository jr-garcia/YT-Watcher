from json import loads
from os import path, remove, listdir, makedirs

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
    try:
        from .youtube_dl import version
        localVersion = version.__version__
    except ImportError:
        localVersion = '1980.01.01'
    from datetime import date
    global CHECKED
    try:
        if CHECKED:
            if useYield:
                yield False
            else:
                return
        CHECKED = True
        data = download('https://api.github.com/repos/rg3/youtube-dl/releases/latest')
        parsedData = loads(data.decode('utf-8'))

        remoteVersion = parsedData['tag_name']
        year, month, day = [int(d) for d in remoteVersion.split('.')]
        remoteDate = date(year, month, day)
        if not noCheck:
            year, month, day = [int(d) for d in localVersion.split('.')]
            localDate = date(year, month, day)
            isNewVersion = remoteDate > localDate
        else:
            isNewVersion = True

        if useYield:
            yield isNewVersion

        if isNewVersion:
            if noCheck:
                reason = 'missing'
            else:
                reason = 'outdated'

            message = 'Youtube-DL is {}.\n'.format(reason) + 'New version ({}) will be downloaded now.'.format(remoteVersion)
            if showMessage:
                QMessageBox.warning(None, 'Tool {}'.format(reason), message, QMessageBox.Ok)
            else:
                print(message)

            package = download(parsedData['tarball_url'])
            if not path.exists(CACHESPATH):
                makedirs(CACHESPATH)
            _packageTar = path.join(CACHESPATH, '_temp_ytd.tar')
            
            with open(_packageTar, 'wb') as file:
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
