from __future__ import print_function
from PySide.QtCore import *
from PySide.QtGui import *
import sys
from os import path, listdir, mkdir
from multiprocessing import Pool, TimeoutError as PoolTimeOutError
import webbrowser
from json import loads, dump, load
from os import listdir, remove

from .Downloading import download
from .Searching import *
from ._paths import *
from .Listing import VideoItem

mainWin = None

try:
    import urllib3 as ulib
except ImportError:
    import urllib as ulib


class MainWindow(QMainWindow):
    newThumbReady = Signal(str, object)

    def __init__(self, app):
        super(MainWindow, self).__init__()
        self.videosCache = {}
        self.thumbsCache = {}
        self.thumbnailPixmaps = {}

        self.loadVideosCache()
        self.fillThumbsCache()

        self.searchers = {}

        self.movieSearch = QMovie(path.join(iconPath, 'loading', 'loading.gif'))
        # self.movieSearch.setBackgroundColor(QColor(255, 255, 255))
        emptyPM = QPixmap(QSize(32, 32))
        emptyPM.fill(QColor(0, 0, 0, 0))
        self.iconSearching = QIcon(emptyPM)
        self.iconPaused = QIcon(path.join(brightPath, 'pause.png'))
        self.iconReady = QIcon(path.join(brightPath, 'clock.png'))
        self.iconSearch = QIcon(path.join(brightPath, 'ifind.png'))
        self.movieSearch.updated.connect(self.updateLoadingIcon)

        self.setWindowTitle('YT Filterer')
        self.setMinimumSize(QSize(700, 400))
        self._central = QWidget(self)
        self.setCentralWidget(self._central)

        self.layoutMain = QHBoxLayout(self._central)
        self.splitterMain = QSplitter()
        self.setLayout(self.layoutMain)
        self.layoutMain.addWidget(self.splitterMain)

        self._addWidgets()
        self._addToolbar()
        self.statusBar().showMessage('Ready')
        self.resize(QSize(800, 600))
        # self.setWindowIcon(QtGui.QIcon('web.png'))
        self.center()
        self.searchBox = SearchBox(self, app, self.iconSearch)
        self.searches = {}

        self.movieSearch.start()  # todo: start at first item addition

        # self.timerConection = QTimer()
        # self.timerConection.timeout.connect(self.checkConnection)
        # self.timerConection.start(5000)

        self.show()

        # self.updateYTD()

        self.newSearch()

    def updateLoadingIcon(self):
        pix = self.movieSearch.currentPixmap()
        self.iconSearching = QIcon(pix)
        for s in self.searches.values():
            item = self.listSearches.item(s.index)
            searchStatus = s.status
            if searchStatus == SearchStatesEnum.searching:
                item.setIcon(self.iconSearching)
            elif searchStatus == SearchStatesEnum.readyToSearch:
                item.setIcon(self.iconReady)
            elif searchStatus == SearchStatesEnum.paused:
                item.setIcon(self.iconPaused)

    def center(self):
        qr = self.frameGeometry()
        cp = QDesktopWidget().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())

    def _addWidgets(self):
        self.listSearches = QListWidget(self)

        self.listSearches.setMinimumWidth(100)
        self.listSearches.setMaximumWidth(200)
        self.splitterMain.setSizes([.2, 1])
        self.listSearches.doubleClicked.connect(self.editSearch)

        self.splitterMain.addWidget(self.listSearches)

        self.tabPreviews = QTabWidget()
        self.listPreviews = QListWidget()
        self.listPreviews.itemDoubleClicked.connect(self.openVideoInBrowser)
        self.spinboxRefreshTime = QSpinBox()
        self.spinboxRefreshTime.setValue(1)

        layoutPreviews = QVBoxLayout()
        # layoutPreviewTools = QHBoxLayout()
        #
        # layoutPreviewTools.addWidget(QLabel('Refresh time:'))
        # layoutPreviewTools.addWidget(self.spinboxRefreshTime)
        # layoutPreviewTools.addWidget(QLabel('minutes'))

        # layoutPreviews.addLayout(layoutPreviewTools)
        layoutPreviews.addWidget(self.listPreviews)

        self.widgetPreviews = QWidget()
        self.widgetPreviews.setLayout(layoutPreviews)

        self.splitterMain.addWidget(self.tabPreviews)
        self.tabPreviews.addTab(QWidget(), self.iconReady, 'New search')

    def _addToolbar(self):
        searchAction = QAction(self.iconSearch, 'New Search', self)
        searchAction.setShortcut('Ctrl+S')
        searchAction.triggered.connect(self.newSearch)

        self.toolbar = self.addToolBar('main')
        toolbar = self.toolbar
        toolbar.addAction(searchAction)
        toolbar.setIconSize(QSize(32, 32))
        toolbar.addSeparator()
        toolbar.addWidget(QLabel('Update every:'))
        toolbar.addWidget(self.spinboxRefreshTime)
        toolbar.addWidget(QLabel('min'))

    def editSearch(self):
        search = self.searches[self.listSearches.selectedItems()[0].text()]
        self.newSearch(search, True)

    def newSearch(self, search=None, isEdit=False):
        if search is None:
            search = Search(self.videosCache, self.thumbsCache, self.searchReady, self.thumbReady, 'cat',
                            status=SearchStatesEnum.readyToSearch)
        search = self.searchBox.show(search, isEdit)
        if search:
            word = search.word
            if search.status == SearchStatesEnum.readyToSearch:
                icon = self.iconReady
            elif search.status == SearchStatesEnum.paused:
                icon = self.iconPaused
            if word in self.searches.keys():
                if not isEdit:
                    res = QMessageBox.question(self, 'Duplicated search', 'Search exist. Replace?', QMessageBox.Yes,
                                               QMessageBox.No)
                else:
                    self.listSearches.item(self.searches[search.word].index).setIcon(icon)
                    res = QMessageBox.Yes
                if res == QMessageBox.No:
                    return
            else:
                item = QListWidgetItem(icon, search.word)
                self.listSearches.insertItem(len(self.searches), item)

            search.index = self.listSearches.count() - 1
            self.searches[word] = search

            search.setTimer(self.spinboxRefreshTime.value() * 60)
            search.callback = self.searchReady
            search.setReady()

            self.tabPreviews.addTab(self.widgetPreviews, icon, search.word)

    def searchReady(self, word, result):
        videoID = result['id']
        if videoID not in self.videosCache.keys():
            self.videosCache[videoID] = result
        self.addVideoItem(result)

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

    def addVideoItem(self, data):
        item = QListWidgetItem('')
        item.setSizeHint(QSize(0, 200))
        videoID = data['id']
        if videoID in self.thumbsCache.keys():
            thumbPix = self.retrieveThumbnail(videoID)
        else:
            thumbPix = None
        newVideoItem = VideoItem(data, self, thumbPix)
        self.newThumbReady.connect(newVideoItem.thumbArrived)
        self.listPreviews.addItem(item)
        self.listPreviews.setItemWidget(item, newVideoItem)

    def editSearchCallback(self, search):
        self.newSearchCallback(search, True)

    def closeEvent(self, *args, **kwargs):
        self.dumpVideosCache()

        for s in self.searches.values():
            s.terminate()

        super(MainWindow, self).closeEvent(*args, **kwargs)

    def dumpVideosCache(self):
        if len(self.videosCache.keys()) > 0:
            with open(videoInfosCacheFilePath, 'w') as cache:
                dump(self.videosCache, cache, indent=4)

    def loadVideosCache(self):
        if path.exists(videoInfosCacheFilePath):
            with open(videoInfosCacheFilePath, 'r') as cache:
                try:
                    self.videosCache = load(cache)
                except:
                    remove(videoInfosCacheFilePath)

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

    def openVideoInBrowser(self, item):
        view = self.listPreviews.itemWidget(item)
        webbrowser.open(view.videoData['webpage_url'])

    def fillThumbsCache(self):
        if not path.exists(cachedThumbsPath):
            mkdir(cachedThumbsPath)

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

    def updateYTD(self):
        """
        With info from https://stackoverflow.com/a/26454035
        """
        from .youtube_dl import version
        try:
            data = download('https://api.github.com/repos/rg3/youtube-dl/releases/latest')
            parsedData = loads(data.decode('utf-8'))

            if parsedData['tag_name'] > version.__version__:
                QMessageBox.warning(self, 'Tool outdated', 'Youtube-DL is outdated.\n'
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
    mainWin = MainWindow(app)
    sys.exit(app.exec_())
