from __future__ import print_function

import sys
from json import dump, load
from multiprocessing import TimeoutError as PoolTimeOutError
from os import listdir, mkdir, remove

from .updateYT_DL import is_YTDL_importable, updateYTD

CACHEFILEEXT = '.cache'

if not is_YTDL_importable():
    updateYTD(True)

from .Listing import *
from .Searching import *
from ._paths import *

mainWin = None

try:
    import urllib3 as ulib
except ImportError:
    import urllib as ulib


class MainWindow(QMainWindow):
    newThumbReady = Signal(str, object)

    def __init__(self, app):
        super(MainWindow, self).__init__()
        self.videoInfosCache = {}
        self.thumbsCache = {}
        self.thumbnailPixmaps = {}

        if not path.exists(CACHESPATH):
            mkdir(CACHESPATH)

        self.loadVideoInfosCache()
        self.loadThumbsCache()

        self.searchers = {}

        self.movieSearch = QMovie(path.join(iconPath, 'loading', 'loading.gif'))
        emptyPM = QPixmap(QSize(32, 32))
        emptyPM.fill(QColor(0, 0, 0, 0))
        self.iconSearching = QIcon(emptyPM)
        self.iconPaused = QIcon(path.join(brightPath, 'pause.png'))
        self.iconReady = QIcon(path.join(brightPath, 'clock.png'))
        self.iconSearch = QIcon(path.join(brightPath, 'ifind.png'))
        self.iconAdd = QIcon(path.join(brightPath, 'plus_green.png'))
        self.iconTools = QIcon(path.join(brightPath, 'tools.png'))
        self.movieSearch.updated.connect(self.updateLoadingIcon)

        self.setWindowTitle('YT Watcher')
        self.setMinimumSize(QSize(700, 400))

        self._addWidgets()
        # self.statusBar().showMessage('Ready')
        self.resize(QSize(800, 600))
        self.setWindowIcon(QIcon(path.join(iconPath, 'logo.png')))
        self.center()
        self.searches = {}

        self.movieSearch.start()  # todo: start at first item addition

        # self.timerConection = QTimer()
        # self.timerConection.timeout.connect(self.checkConnection)
        # self.timerConection.start(5000)

        self.show()
        self.loadSearches()
        # updateYTD()

        if len(self.searches.items()) == 0:
            self.previewsWidget._queryNewSearch()

    def updateLoadingIcon(self):
        pix = self.movieSearch.currentPixmap()
        self.iconSearching = QIcon(pix)
        for s in self.searches.values():
            searchStatus = s.status
            if s.isSearching():
                icon = self.iconSearching
            elif searchStatus == SearchStatesEnum.readyToSearch:
                icon = self.iconReady
            else:  # searchStatus == SearchStatesEnum.paused:
                icon = self.iconPaused
            self.previewsWidget.tabWidget.setTabIcon(s.index, icon)

    def center(self):
        qr = self.frameGeometry()
        cp = QDesktopWidget().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())

    def _addWidgets(self):
        prevWid = PreviewWidget(self.iconAdd, self.iconTools)
        prevWid.newSearchRequested.connect(self.newSearchRequested)
        prevWid.tabChanged.connect(self.focusedSearchChanged)
        self.previewsWidget = prevWid

        self.setCentralWidget(self.previewsWidget)

        self.layoutMain = QHBoxLayout()
        self.setLayout(self.layoutMain)

        self.searchBox = SearchPropertiesWidget(self)
        dockSearchProperties = QDockWidget(self)
        dockSearchProperties.setEnabled(False)
        dockSearchProperties.setWidget(self.searchBox)
        dockSearchProperties.resize(dockSearchProperties.size())
        dockSearchProperties.resize(100, dockSearchProperties.size().height())
        dockSearchProperties.setWindowTitle('Search Properties')
        dockSearchProperties.setWindowIcon(self.iconSearch)
        self.dockSearchProperties = dockSearchProperties
        self.addDockWidget(Qt.LeftDockWidgetArea, dockSearchProperties)

    def focusedSearchChanged(self, word):
        if word == '[no searches]':
            self.dockSearchProperties.setEnabled(False)
        else:
            self.dockSearchProperties.setEnabled(True)
            self.searchBox.refresh(self.searches[word])

    def newSearchRequested(self, word):
        if word in self.searches.keys():
            QMessageBox.critical(self, 'Wrong data', 'Word is already added to searches', QMessageBox.Ok)
            return

        self.createNewSearch(word)

    def createNewSearch(self, word, fromInit=False):
        if fromInit:
            status = SearchStatesEnum.paused
        else:
            status = SearchStatesEnum.readyToSearch

        search = Search(self.videoInfosCache, self.thumbsCache, self.searchReady, self.thumbReady, word, None, status)

        search.callback = self.searchReady
        self.searches[word] = search

        if search.status == SearchStatesEnum.readyToSearch:
            icon = self.iconReady
            search.setReady()
        else:  # search.status == SearchStatesEnum.paused:
            icon = self.iconPaused

        self.previewsWidget.add(search, icon)

        return search

    def searchReady(self, word, result):
        videoID = result['id']
        if videoID not in self.videoInfosCache.keys():
            self.dumpVideoInfo(videoID, result)
            self.videoInfosCache[videoID] = result

        if videoID in self.thumbsCache.keys():
            thumbPix = self.retrieveThumbnail(videoID)
        else:
            thumbPix = None

        newVideoItem = self.previewsWidget.updateSearch(word, result, thumbPix)
        self.newThumbReady.connect(newVideoItem.thumbArrived)

    def retrieveThumbnail(self, videoID):
        if videoID not in self.thumbnailPixmaps.keys():
            self.thumbnailPixmaps[videoID] = QPixmap(self.thumbsCache[videoID])
        return self.thumbnailPixmaps[videoID]

    def thumbReady(self, result):
        data, searchType = result
        videoID, thumbPath = data
        self.thumbsCache[videoID] = thumbPath
        with open(thumbsCacheFilePath, 'a') as tc:
            print(videoID, file=tc)
        self.newThumbReady.emit(videoID, self.retrieveThumbnail)

    def editSearchCallback(self, search):
        self.newSearchCallback(search, True)

    def closeEvent(self, *args, **kwargs):
        for s in self.searches.values():
            s.terminate()

        self.dumpSearches()

        super(MainWindow, self).closeEvent(*args, **kwargs)

    def dumpVideoInfo(self, videoID, info):
        if path.exists(cachedInfosPath):
            filenames = listdir(cachedInfosPath)

            fileName = '_' + videoID + CACHEFILEEXT
            if fileName not in filenames:
                filePath = path.join(cachedInfosPath, fileName)
                with open(filePath, 'x') as file:
                    dump(info, file, indent=4)

    def loadVideoInfosCache(self):
        self.createFolderIfAbscent(cachedInfosPath)

        for fileName in listdir(cachedInfosPath):
            fpath = path.join(cachedInfosPath, fileName)
            videoID, ext = path.splitext(fileName)
            videoID = videoID[1:]
            with open(fpath, 'r') as info:
                infoDict = load(info)
            self.thumbsCache[videoID] = infoDict

    def dumpSearches(self):
        for word, s in self.searches.items():
            fileName = '_' + word + CACHEFILEEXT
            filePath = path.join(searchesPath, fileName)
            with open(filePath, 'w') as file:
                searchInitDict = {'seconds': s.seconds, 'status': s.status,
                                  'excludeds': s.excludeds, 'unit': s._unit}
                dump(searchInitDict, file, indent=4)

    def loadSearches(self):
        self.createFolderIfAbscent(searchesPath)

        for fileName in listdir(searchesPath):
            fpath = path.join(searchesPath, fileName)
            word, ext = path.splitext(fileName)
            word = word[1:]
            with open(fpath, 'r') as info:
                search = self.createNewSearch(word, True)
                searchInitDict = load(info)
                search.seconds = searchInitDict['seconds']
                status = searchInitDict['status']
                search.excludeds = searchInitDict['excludeds']
                search._unit = searchInitDict['unit']
                if status == SearchStatesEnum.readyToSearch:
                    search.forceSearchNow()

            remove(fpath)

    def loadThumbsCache(self):
        self.createFolderIfAbscent(cachedThumbsPath)

        if not path.exists(thumbsCacheFilePath):
            with open(thumbsCacheFilePath, 'x'):
                pass

        with open(thumbsCacheFilePath, 'r') as tc:
            for videoID in tc:
                videoID = videoID.split()[0]
                for f in listdir(cachedThumbsPath):
                    if f.startswith('_' + videoID):
                        self.thumbsCache[videoID] = path.join(cachedThumbsPath, f)
                        break

    def createFolderIfAbscent(self, folderPath):
        if not path.exists(folderPath):
            mkdir(folderPath)

    def connectionCallback(self, res):
        if res:
            self.statusBar().showMessage('Connection Error!')
        else:
            self.statusBar().showMessage('Ready')

    def checkConnection(self):
        try:
            self.pool.map_async(_pickleableCheck, [''], callback=self.connectionCallback).get(1)
        except PoolTimeOutError:
            pass
        except Exception:
            raise

    def stopSearches(self):
        for s in self.searches:
            s._externalPause('pause')


def _pickleableCheck(dummy):
    con = ulib.connection_from_url('https://youtube.com')
    try:
        con.request('GET', '/', retries=None)
        return None
    except ulib.exceptions.HTTPError as err:
        return err
    except Exception:
        raise


def _runMainWindow():
    app = QApplication('')
    setApp(app)
    mainWin = MainWindow(app)
    sys.exit(app.exec_())
