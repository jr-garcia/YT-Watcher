from multiprocessing import Queue, cpu_count
from queue import Empty, Full

from PySide.QtCore import QObject, QTimer, Signal
from PySide.QtGui import *

from .ParallellSearcher import Searcher, NonValidDataError, TaskTypesEnum, ErrorTypesEnum, RemoteError, TaskResult
# from .youtube_dl.utils import *
from .updateYT_DL import updateYTD


class SearchStatesEnum(object):
    paused = 'paused'
    readyToSearch = 'ready'
    error = 'error'


class SortingEnum(object):
    newest = 'Newest'
    oldest = 'Oldest'
    views = 'Views'
    likes = 'Likes'
    lenght = 'Lenght'


class Search(QObject):
    notRead = Signal()
    reStartRequired = Signal()
    shutdownRequired = Signal(str, str)

    def __init__(self, videoInfosCache, thumbsCache, baseCallback, thumbsCallback, pool, word='', excludeds=None,
                 status=SearchStatesEnum.readyToSearch):
        super(Search, self).__init__()
        self.thumbsCallback = thumbsCallback
        self.thumbsCache = thumbsCache
        self.videoInfosCache = videoInfosCache
        if excludeds is None:
            excludeds = []
        self.word = word
        self.excludeds = excludeds
        self.status = status
        self.index = -1
        self._miliseconds = 2 * 60 * 1000
        self.baseCallback = baseCallback
        self.results = {}
        self.timer = QTimer(self)
        self.timer.stop()
        self.timer.timeout.connect(self._performSearch)

        self._unit = 'minutes'
        self._lastFoundCount = 0

        self._isFirstRun = True
        self.error = None
        self._externalPause = False

        self.viewMode = QListView.ListMode
        self._searchMode = 1
        self._maxResults = 50

        self.pool = pool

        self._isSearching = False
        self._isRead = True

        self._sorting = SortingEnum.newest

        self.task = PoolableTask(self._searchMode, self._maxResults)

    @property
    def sorting(self):
        return self._sorting

    @sorting.setter
    def sorting(self, value):
        self._sorting = value

    @property
    def maxResults(self):
        return self._maxResults

    @maxResults.setter
    def maxResults(self, value):
        self._maxResults = value
        self.task.maxResults = value

    @property
    def isRead(self):
        return self._isRead

    @isRead.setter
    def isRead(self, value):
        self._isRead = value

    def isSearching(self):
        return self._isSearching

    @property
    def seconds(self):
        return int(self._miliseconds / 1000)

    @seconds.setter
    def seconds(self, value):
        self._miliseconds = value * 1000
        self.resetTimer()

    def __repr__(self):
        return '\'{}\' , {} exclusions, {}'.format(self.word, len(self.excludeds), self.status)

    def _performSearch(self):
        self.setSearching()
        self.pool.appendTask(self.task(self.word, TaskTypesEnum.word), self._resultsCallback)

    def _resultsCallback(self, returnValue):
        if not isinstance(returnValue, TaskResult):
            self.terminate()
            self.shutdownRequired(self.word, 'Return value is not of class \'TaskResult\'')

        result = returnValue.data
        taskType = returnValue.taskType

        if taskType == TaskTypesEnum.error:
            errorType = result.errorType
            if errorType == ErrorTypesEnum.NonValidData:
                gen = updateYTD(showMessage=False, useYield=True)
                isNewer = next(gen)
                if isNewer:
                    res = QMessageBox.critical(None, 'Downloader error', 'An error has ocurred and '
                                               'there is a new Youtube-DL version that might solve the problem.\n'
                                               'Would you like to update and restart now?', QMessageBox.Yes,
                                               QMessageBox.No)
                    if res == QMessageBox.Yes:
                        next(gen)
                        self.reStartRequired.emit()
            elif errorType == ErrorTypesEnum.PageNonAccesible:
                QMessageBox.critical(None, 'Downloader error', 'A network related error has ocurred.\n '
                                                               'Is Internet working?\n', QMessageBox.Ok)
                self.setSearchFinished()
                        
        elif taskType == TaskTypesEnum.word:
            self._lastFoundCount = len(result['entries'])

            for video in result['entries']:
                videoID = video['id']
                if videoID in self.results.keys():
                    continue
                cachedVideoResult = self.videoInfosCache.get(videoID)
                if cachedVideoResult is None:
                    self.pool.appendTask(self.task(video['url'], TaskTypesEnum.video), self._resultsCallback)
                else:
                    self._resultsCallback(TaskResult(cachedVideoResult, TaskTypesEnum.video))
        elif taskType == TaskTypesEnum.video:
            self._lastFoundCount -= 1
            if self._lastFoundCount == 0:
                self.setReady()
            videoID = result['id']
            self.results[videoID] = result
            if videoID not in self.thumbsCache.keys():
                thumbURL = result['thumbnail']
                self.pool.appendTask(self.task((thumbURL, videoID), TaskTypesEnum.thumb), self._resultsCallback)

            self.isRead = False
            self.baseCallback(self.word, result)
        else:
            self.thumbsCallback(result)

    def setSearching(self):
        self.timer.stop()
        self._isSearching = True

    def setReady(self):
        self._isSearching = False
        miliseconds = 1 if self._isFirstRun else self._miliseconds
        self._isFirstRun = False
        self.status = SearchStatesEnum.readyToSearch
        self.timer.start(miliseconds)

    def setSearchFinished(self):
        if self.status != SearchStatesEnum.paused:
            self.setReady()
        else:
            self._isSearching = False

    def resetTimer(self):
        self.timer.stop()
        if self.status != SearchStatesEnum.paused:
            self.timer.start(self._miliseconds)

    @property
    def searchMode(self):
        return self._searchMode

    @searchMode.setter
    def searchMode(self, value):
        self._searchMode = value
        self.task.sorting = value

    def forceSearchNow(self):
        self._performSearch()

    def setPaused(self):
        self.timer.stop()
        self.status = SearchStatesEnum.paused

    def terminate(self):
        self.timer.stop()

    def _externalPause(self, state):
        self.queue.put_nowait(state)


class PoolableTask(object):
    def __init__(self, sorting, maxResults):
        self.sorting = sorting
        self.maxResults = maxResults
        self.task = None
        self.taskType = None

    def __call__(self, task, taskType):
        newTask = PoolableTask(self.sorting, self.maxResults)
        newTask.task = task
        newTask.taskType = taskType
        return newTask

    def __repr__(self):
        return str(self.task) + '-' + str(self.taskType)

    def __getitem__(self, item):
        if item == 0:
            return self.task
        elif item == 1:
            return self.taskType
        else:
            raise IndexError('wrong index for task')


class Pool(QObject):
    poolCrashed = Signal(str)

    def __init__(self, number=cpu_count(), *args, **kwargs):
        super(Pool, self).__init__(*args, **kwargs)
        self._available = []
        self.searchers = {}
        self.tasks = []
        self.remotes = {}
        self.locals = {}
        self.callbacks = {}
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)

        for i in range(number):
            self.createRemoteSearcher()

    def createRemoteSearcher(self):
        s = Searcher()
        sid = id(s)
        self.searchers[sid] = s
        client = Queue()
        client.cancel_join_thread()
        self.locals[sid] = client
        self.remotes[sid] = s.prepareConnections(client)
        s.start()
        self._available.append(sid)

    def start(self):
        self.timer.start(100)

    def appendTask(self, task, callback):
        if not isinstance(task, PoolableTask):
            raise TypeError('task to send must be of type \'PoolableTask\' not \'{}\''.format(type(task)))

        self.tasks.append((task, callback))

    def update(self):
        while len(self._available) > 0:
            if len(self.tasks) == 0:
                break
            else:
                sid = self._available[0]
                try:
                    task, callback = self.tasks[0]
                    local = self.locals.get(sid)
                    local.put(task, timeout=1)
                    self.tasks.pop(0)
                    if callback is not None:
                        self.callbacks[sid] = callback
                        self._available.pop(0)
                except Full:
                    pass
                except Exception as ex:
                    self.terminate()
                    self.poolCrashed.emit(str(ex))
                    raise ex

        newRemoteNeeded = False
        for ID, remote in self.remotes.items():
            try:
                result = remote.get_nowait()
                if isinstance(result, RemoteError):
                    QMessageBox.critical(None, 'Critical error', 'A fatal error ocurred in ParallellSearcher. \n'
                                                                 'Please restart YT Watcher. If the error persist, '
                                                                 'report it.')
                    raise RuntimeError(result.errorData)
                elif result.taskType == TaskTypesEnum.error:
                    print('Remote error:' + str(result.data.errorData))
                    if result.data.errorType == ErrorTypesEnum.Other:
                        newRemoteNeeded = True
                        return
                    self._available.append(ID)
                    self.callbacks[ID](result)
                else:
                    self._available.append(ID)
                    self.callbacks[ID](result)
            except Empty:
                pass
            except Exception as ex:
                self.terminate()
                self.poolCrashed.emit(str(ex))
                raise ex

        if newRemoteNeeded:
            self.createRemoteSearcher()

    def terminate(self):
        self.timer.stop()
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
