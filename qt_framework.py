# -*- coding: utf-8 -*-
"""
Created on Sat May  4 22:07:54 2013

@author: matt

Qt-specific code for creating UI elements from objects
decorated with ui_decorators
"""
from ui_decorators import *
#UI creation from properties:
import PySide.QtCore
import PySide.QtGui
from Queue import Queue

_bool_checkstate_map = {True: PySide.QtCore.Qt.CheckState.Checked,
       False: PySide.QtCore.Qt.CheckState.Unchecked,
       None: PySide.QtCore.Qt.CheckState.PartiallyChecked}
       
def _bool_to_checkstate(b):
    """
    Convert a python object into a Qt CheckState.
    Returns Checked for True, Unchecked for False,
    and PartiallyChceked for anything else
    
    >>> _bool_to_checkstate(True)
    PySide.QtCore.Qt.CheckState.Checked
    >>> _bool_to_checkstate(False)
    PySide.QtCore.Qt.CheckState.Unchecked
    >>> _bool_to_checkstate(None)
    PySide.QtCore.Qt.CheckState.PartiallyChecked
    >>> _bool_to_checkstate(34)
    PySide.QtCore.Qt.CheckState.PartiallyChecked
    """
    return _bool_checkstate_map.get(b, _bool_checkstate_map[None])
   
def _checkstate_to_bool(cs):
    """
    Convert a Qt CheckState int a python bool or None.
    Returns True for Checked, False for Unchecked or None.
    
    >>> _checkstate_to_bool(PySide.QtCore.Qt.CheckState.Checked)
    True
    >>> _checkstate_to_bool(PySide.QtCore.Qt.CheckState.Unchecked)
    False
    >>> _checkstate_to_bool(PySide.QtCore.Qt.CheckState.PartiallyChecked) is None
    True
    """
    for key, val in _bool_checkstate_map.iteritems():
        if val==cs:
            return key
            
class Framework(FrameworkBase, PySide.QtCore.QObject):
    """
    Qt Framework class
    We derive from QObject to use signals, allowing us to implement
    the run_on_ui_thread function by adding the function to a Queue,
    emitting a signal and having ourselves connected to that signal.
    The code for the received signal is in the UI thread, so we then
    call any functions in the queue.
    """
    _queue_updated = PySide.QtCore.Signal()
    def __init__(self):
        PySide.QtCore.QObject.__init__(self)
        self.q = Queue()
        self._queue_updated.connect(self.on_queue_updated)

        self.app = PySide.QtGui.QApplication("Qt")
        self.main = PySide.QtGui.QMainWindow()
        self.main.setDockOptions(self.main.AllowNestedDocks | self.main.AllowTabbedDocks)
        self.changing_widgets = []

    def close(self):
        self.app.quit()

    def on_queue_updated(self):
        while not self.q.empty():
            f = self.q.get()
            f()

    def run_on_ui_thread(self, f):
        self.q.put(f)
        self._queue_updated.emit()

    def get_main_window(self):
        return self.main

    def get_widgets_for_method(self, method):
        """
        Return a list of (text, widget) tuples
        """
        ret = []
        listenerfunc = getattr(method, "listeners", None)
        method_name = method.__func__.__name__
        def add_widget(name, widget, found_attr, update_widget=None):
            if name is None:
                name = method_name
            if update_widget:
                # we wrap the update function in a check to make sure we're
                #not in the middle of changing the control
                update_widget = updating_widget(widget, update_widget)
                # we subscribe to changes from any listeners
                if listenerfunc:
                    listenerfunc(method.im_self).append(update_widget)
                # if a get func is supplied we use it to initialize the widget
                if found_attr.get("getfunc"):
                    curval=found_attr.get("getfunc")(method.im_self)
                    update_widget(curval)
            ret.append((name, widget))
            
        def widget_changing(widget, func):
            # we wrap change func so that we know which UI elements are changing
            # NB we can change a textedit which can change a slider. We want to
            # ignore the slider value and the text value, so we need a list of
            # changing widgets
            def setter(*args):
                self.changing_widgets.append(widget)
                try:
                    ret = func(*args)
                finally:
                    self.changing_widgets.remove(widget)
                return ret
            return setter
                
        def updating_widget(widget, func):
            def updater(*args):
                if widget not in self.changing_widgets:
                    return func(*args)
            return updater
            
        if hasattr(method, "_slider"):
            widget = PySide.QtGui.QSlider(PySide.QtCore.Qt.Orientation.Horizontal)
            widget.setMaximum(method._slider["maximum"])
            widget.setMinimum(method._slider["minimum"])
            widget.valueChanged.connect(widget_changing(widget,
                lambda x, method=method: method(x / method._slider["scale"])))
            update_widget = lambda newv, method=method, widget=widget: widget.setValue(newv * method._slider["scale"])
            add_widget(None, widget, method._slider, update_widget)
        if hasattr(method, "_button"):
            widget = PySide.QtGui.QPushButton(method_name)
            widget.clicked.connect(lambda method=method: method())
            add_widget("", widget, method._button)      
        if hasattr(method, "_combobox"):
            widget = PySide.QtGui.QComboBox()
            widget.addItems(map(str, method._combobox["options"]))
            widget.currentIndexChanged.connect(widget_changing(widget,
                lambda x, method=method: method(method._combobox["options"][x])))
            update_widget = lambda newv, method=method, widget=widget: widget.setCurrentIndex(method._combobox["options"].index(newv))      
            add_widget(None, widget, method._combobox, update_widget)
        if hasattr(method, "_textbox"):
            widget = PySide.QtGui.QLineEdit()
            widget.textEdited.connect(widget_changing(widget,
                                       lambda x, method=method: method(x)))
            update_widget = lambda newv, widget=widget: widget.setText(str(newv))
            add_widget(None, widget, method._textbox, update_widget)
        if hasattr(method, "_checkbox"):               
            widget = PySide.QtGui.QCheckBox()
            widget.stateChanged.connect(widget_changing(widget,
                lambda x, method=method: method(_checkstate_to_bool(x))))
            update_widget = lambda newv, widget=widget: widget.setCheckState(_bool_to_checkstate(newv))
            add_widget(None, widget, method._checkbox, update_widget)
        return ret

    def get_obj_widget(self, obj):
        layout = PySide.QtGui.QFormLayout()
        for p in dir(obj):
            v = getattr(obj, p)
            if not isinstance(v, types.MethodType):
                continue
            widgets = self.get_widgets_for_method(v)
            for name, widget in widgets:
                layout.addRow(name, widget)
        
        d=PySide.QtGui.QDockWidget(obj.__class__.__name__)
        d.setWidget(PySide.QtGui.QWidget())
        d.widget().setLayout(layout)
        return d
        
    def display_widgets(self, ws):
        for w in ws:
            self.main.addDockWidget(PySide.QtCore.Qt.LeftDockWidgetArea, w)
        self.main.show()
        self.app.exec_()
 