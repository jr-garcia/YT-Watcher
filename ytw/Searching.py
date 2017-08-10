from PySide.QtGui import *
from PySide.QtCore import QTimer, QObject

from .ParallellSearcher import Searcher, SearchTypesEnum
from multiprocessing import Queue, cpu_count, Pipe
from queue import Empty, Full
from collections import OrderedDict


class SearchStatesEnum(object):
    paused = 'paused'
    searching = 'searching'
    readyToSearch = 'ready'
    error = 'error'


class Search(QObject):
    def __init__(self, videosCache, thumbsCache, baseCallback, thumbsCallback, word='', excludeds=None, status=SearchStatesEnum.readyToSearch,
                 ):
        super(Search, self).__init__()
        self.thumbsCallback = thumbsCallback
        self.thumbsCache = thumbsCache
        self.videosCache = videosCache
        if excludeds is None:
            excludeds = []
        self.word = word
        self.excludeds = excludeds
        self.status = status
        self.index = -1
        self._seconds = 0
        self.baseCallback = baseCallback
        self.results = []
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.performSearch)
        # self.timerResults = QTimer(self)
        # self.timerResults.timeout.connect(self._resultsCallback)
        # self.timerResults.start(1)
        self._isFirstRun = True
        self.error = None
        self._externalPause = False

        self.resultsQueue = []

        # if status == SearchStatesEnum.readyToSearch:
        #     self.timer.start(1)
        #     self._isFirstRun = False

        self.pool = Pool(4)
        self.pool.start()

    def setTimer(self, seconds):
        self._seconds = seconds * 1000

    def __repr__(self):
        return '\'{}\' , {} exclusions, {}'.format(self.word, len(self.excludeds), self.status)

    def performSearch(self):
        self._setSearching()
        self.pool.appendTask((self.word, SearchTypesEnum.word), self._resultsCallback)

    def _resultsCallback(self, returnValue):

        if not isinstance(returnValue, tuple):
            if issubclass(type(returnValue), YoutubeDLError):
                self.status = SearchStatesEnum.error
                self.error = returnValue
                return
            else:
                self.terminate()
                raise returnValue
        
        result, searchType = returnValue

        if searchType == SearchTypesEnum.word:
            self.setReady()
            for video in result['entries']:
                videoID = video['id']
                if videoID in self.results:
                    continue
                if videoID not in self.videosCache.keys():
                    self.pool.appendTask((video['url'], SearchTypesEnum.video), self._resultsCallback)
                else:
                    cachedVideoResult = self.videosCache[videoID]
                    self._resultsCallback((cachedVideoResult, SearchTypesEnum.video))
        elif searchType == SearchTypesEnum.video:
            videoID = result['id']
            self.results.append(videoID)
            if videoID not in self.videosCache.keys():
                self.videosCache[videoID] = result
            if videoID not in self.thumbsCache:
                thumbURL = result['thumbnail']
                self.pool.appendTask(((thumbURL, videoID), SearchTypesEnum.thumb), self.thumbsHandler)

            self.baseCallback(self.word, result)

    def thumbsHandler(self, result):
        self.thumbsCallback(result)

    def _setSearching(self):
        # print('Searching for:', self.word)
        self.timer.stop()
        self.status = SearchStatesEnum.searching

    def setReady(self):
        seconds = 1 if self._isFirstRun else self._seconds
        self._isFirstRun = False
        self.status = SearchStatesEnum.readyToSearch
        self.timer.start(seconds)

    def setPaused(self):
        self.timer.stop()
        self.status = SearchStatesEnum.paused

    def terminate(self):
        self.timer.stop()
        # self.timerResults.stop()
        self.pool.terminate()

    def _externalPause(self, state):
        self.queue.put_nowait(state)


class SearchBox(QDialog):
    def __init__(self, parent, app, icon):
        global qApp
        super(SearchBox, self).__init__(parent)
        self.setWindowIcon(icon)
        qApp = app
        mainlay = QVBoxLayout()
        self.setLayout(mainlay)
        self._canceled = False

        glay = QFormLayout()
        mainlay.addLayout(glay)

        self.searchWordEdit = QLineEdit()
        self.searchWordEdit.textEdited.connect(self.switchOk)
        self.excludedEdit = QPlainTextEdit()
        glay.addRow(QLabel('Word'), self.searchWordEdit)
        glay.addRow(QLabel('Exclude terms\n(one per line)'), self.excludedEdit)

        self.startedCheck = QCheckBox('Started')
        self.startedCheck.setChecked(True)
        glay.addWidget(self.startedCheck)

        hlay = QHBoxLayout()
        mainlay.addLayout(hlay)
        self.buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)

        self.buttonBox.accepted.connect(self.ready)
        self.buttonBox.rejected.connect(self.close)
        hlay.addWidget(self.buttonBox)

    def show(self, search, isEdit=False):
        if isEdit:
            self.setWindowTitle('Edit search')
        else:
            self.setWindowTitle('New search')

        self._canceled = False
        self.searchWordEdit.setText(search.word)
        self.searchWordEdit.setEnabled(not isEdit)
        self.startedCheck.setChecked(True if search.status == SearchStatesEnum.readyToSearch else False)
        self.excludedEdit.setPlainText('\n'.join(search.excludeds))
        self.searchWordEdit.setFocus()
        self.switchOk()

        self.setModal(True)
        super(SearchBox, self).show()

        while self.isVisible():
            qApp.processEvents()

        if self.searchWordEdit.text() == '' or self._canceled or self.result() == QDialog.Rejected:
            search.terminate()
            return None
        else:
            excludes = []
            exText = self.excludedEdit.toPlainText()
            if exText != '':
                excludes = exText.split('\n')
            search.terminate()
            newSearch = Search(search.videosCache, search.thumbsCache, search.baseCallback, search.thumbsCallback,
                               self.searchWordEdit.text(), excludes, SearchStatesEnum.readyToSearch if
                               self.startedCheck.isChecked() else SearchStatesEnum.paused)
            return newSearch

    def close(self, *args, **kwargs):
        self._canceled = True
        super(SearchBox, self).close()

    def switchOk(self):
        self.buttonBox.button(QDialogButtonBox.Ok).setEnabled(bool(len(self.searchWordEdit.text())))

    def ready(self):
        self.setResult(QDialog.Accepted)
        self.hide()


class Pool(QObject):
    def __init__(self, number=cpu_count(), *args, **kwargs):
        super(Pool, self).__init__(*args, **kwargs)
        self._available = []
        self._busy = {}
        self.searchers = {}
        self.tasks = []
        self.remotes = {}
        self.locals = {}
        self.callbacks = {}
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)

        for i in range(number):
            s = Searcher()
            sid = id(s)
            self.searchers[sid] = s
            client = Queue()
            self.locals[sid] = client
            self.remotes[sid] = s.prepareConnections(client)
            s.start()
            self._available.append(sid)

    def start(self):
        self.timer.start(1)

    def stop(self):
        self.timer.stop()
            
    def appendTask(self, data, callback):
        self.tasks.append((data, callback))

    def update(self):
        while len(self._available) > 0:
            if len(self.tasks) == 0:
                break
            else:
                sid = self._available[0]
                try:
                    task, callback = self.tasks[0]
                    self.callbacks[sid] = callback
                    self._busy[sid] = sid
                    local = self.locals.get(sid)
                    local.put(task, timeout=1)
                    self._available.pop(0)
                    self.tasks.pop(0)
                except Full:
                    pass
                    # self._busy.pop(sid)
                    # self._available.append(sid)
                except AssertionError:
                    self.terminate()
                except OSError:
                    self.terminate()

        for ID, remote in self.remotes.items():
            qApp.processEvents()
            try:
                result = remote.get_nowait()
                self._busy.pop(ID)
                self._available.append(ID)
                self.callbacks[ID](result)
            except Empty:
                pass
            except OSError:
                self.terminate()
                return

    def terminate(self):
        for c in self.locals.values():
            try:
                c.put_nowait('')
                c.close()
            except OSError:
                pass
            except AssertionError:
                pass

        for s in self.searchers.values():
            s.terminate()
