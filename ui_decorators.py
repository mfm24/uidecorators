# -*- coding: utf-8 -*-
"""
Created on Sat May  4 22:07:54 2013

@author: matt

Tries to allow users to specify simple UI elements for functions
using decorators.

For controls, it makes more sense to decorate the set function, specifying
an optional get function.

def get_volume(self):
    return self.volume

@slider(getfunc=get_volume)
def volume(self, newval):
    self.volume=newval

This is framework agnostic, and needs a framework-specific module to
map a decorated object into a UI. We expect the framework to provide a
closable object called Framework exposing two functions:
Framework.get_obj_widget(o)
Should return a widget compatible with the framework, containing the
elements from the decorated object o. This is designed to be incorporated
in an application already using framewowrk.

Framework.display_widgets(ws)
Displays a list of widgets. These can be created from single or multiple
calls to get_obj_widget.

Optionally, the class can also expose
Framework.get_main_window()
Which returns the main window for the framework.
To display a decorated object o, the following should be fine:
with contextlib.closing(Framework()) as f:
    f.display_widgets([f.get_obj_widget(o)])

We may also want this object to provide a way to execute functions on the
UI thread?
"""
from functools import wraps
import logging
import types


class FrameworkBase(object):
    def get_main_window(self):
        """return a framework-dependant UI Window, if available"""
        raise NotImplementedError("get_main_window")

    def get_obj_widget(self, o):
        """return a framework-dependant widget for the decorated object o"""
        raise NotImplementedError("get_obj_wdiget")

    def display_widgets(self, o):
        """display the framework-dependant widgets ws.
        Blocks until window is dismissed"""
        raise NotImplementedError("display_widgets")

    def run_on_ui_thread(self, f):
        """Runs the function f on a UI thread"""
        raise NotImplementedError("run_on_ui_thread")

    def close(self):
        """Frees up any resources"""
        raise NotImplementedError("close")

    def display(self, o):
        """
        Displays a UI for the decorated object o,
        blocking until dismissed
        """
        self.display_widgets([self.get_obj_widget(o)])

    def get_filename(self, mode="load"):
        """Returns a user specified file name.
        mode should be 'load' or 'save'"""
        raise NotImplementedError("close")


def metadata(name, props):
    """
    Decorator generator that wraps simple metadata to a function.
    Returns the function as is, with an attribute called name
    set to props
    eg
    >>> @metadata("mydata", {1:1, 2:4, "bob":"fish"})
    ... def myfunc():
    ...     print "my func"
    ...
    >>> myfunc.mydata["bob"]
    'fish'
    """
    def metadata_imp(func):
        @wraps(func)
        def wrapped_metadata(*args, **kwargs):
            return func(*args, **kwargs)
        setattr(wrapped_metadata, name, props)
        return wrapped_metadata
    return metadata_imp


# file for some UI stuff where properties determine display properties
def slider(getfunc=None, minimum=0, maximum=100, scale=1):
    """
    Decorator generator creates a decorator to suggest that any UI uses a
    slider to set the given function.

    An optional getfunc, if present, is used to get the current value at
    startup. It must be defined before this decorator is applied!
    See source file for examples
    """
    def my_slider(func):
        # note wraps must be the bottom decorator, meaning it gets
        # applied first, that way w_func has the right name when being sent to
        # notifying setter...
        @metadata("_slider", dict(
            minimum=minimum,
            maximum=maximum,
            scale=scale,
            getfunc=getfunc))
        @notifying_setter
        @wraps(func)
        def w_func(*args, **kwargs):
            return func(*args, **kwargs)
        return w_func
    return my_slider


def combobox(options, getfunc=None):
    """
    Decorator generator creates a decorator to suggest that any UI uses a
    combobox to set the given function.

    options is the set of available options presented to the user, converted
    to strings.
    An optional getfunc, if present, is used to get the current value at
    startup. See source file for examples
    """
    def my_slider(func):
        @metadata("_combobox", dict(
            getfunc=getfunc,
            options=options))
        @notifying_setter
        @wraps(func)
        def w_func(*args, **kwargs):
            return func(*args, **kwargs)
        return w_func
    return my_slider


def checkbox(getfunc=None):
    def my_slider(func):
        @metadata("_checkbox", dict(
            getfunc=getfunc))
        @notifying_setter
        @wraps(func)
        def w_func(*args, **kwargs):
            return func(*args, **kwargs)
        return w_func
    return my_slider


def textbox(getfunc=None):
    def my_slider(func):
        @metadata("_textbox", dict(
            getfunc=getfunc))
        @notifying_setter
        @wraps(func)
        def w_func(*args, **kwargs):
            return func(*args, **kwargs)
        return w_func
    return my_slider


def button(func):
    @metadata("_button", {})
    @wraps(func)
    def w_func(*args, **kwargs):
        return func(*args, **kwargs)
    return w_func


def notifying_setter(func):
    """
    For the method func, adds a 'listeners' method to the function namespace
    which returns a list. Each item in the list gets called with the either
    the same args as the setter or the non-None return value from it
    The list is stored internally in the
    parent object with the name "_{}_listeners",format(func.__name__)
    
    >>> def printfunc(args):
    ...     print args
    ...
    >>> class A:
    ...     @notifying_setter
    ...     def set_val(self, val):
    ...         setattr(self, "val", val)
    ...         print "val set to ", val   
    ...     @notifying_setter
    ...     def set_val2(self, val):
    ...         val = int(val)
    ...         setattr(self, "val2", val)
    ...         print "val2 set to ", val
    ...         return val  # this value is sent to the notification
    ... 
    >>> a = A()
    >>> A.set_val.listeners(a).append(lambda x: printfunc("val listener: %s" % x))
    >>> A.set_val2.listeners(a).append(lambda x: printfunc("val2 listener: %s" % x))
    >>> a.set_val(2)
    val set to  2
    val listener: 2
    >>> a.set_val2("42")
    val2 set to  42
    val2 listener: 42
    42
    """
    # Did think about making this work with functions too:
    # we could specify get/set functions that set either to 
    # self if a class method or globals if a function.
    # Turns out it's hard to tell at decorate time if a function
    # is a class or not. Could try to do at runtime, but it makes
    # things complicated (eg, we'd have to pass get/set functions to the
    # get_listeners function, making it almost unusable outside this function)
    # Also, neither newfunc nor func ever get im_class, (ie neither
    # are identical to A.set_val), so even at run time this isn't trivial.
    listener_list_name = "_{}_listeners".format(func.__name__)
    def get_listeners(self, func=func, name=listener_list_name):
        listeners = getattr(self, listener_list_name, None)
        if listeners is None:
            listeners = []
            setattr(self, name, listeners)
        return listeners
            
    logging.debug("Creating listener obj: %s", listener_list_name)
    @metadata("listeners", get_listeners)
    @wraps(func)
    def newfunc(self, *args, **kwargs):
        # call the original setter, storing the return value
        ret = func(self, *args, **kwargs)
        for l in newfunc.listeners(self):
            if ret is None:
                l(*args, **kwargs)
            else:
                l(ret)
        return ret
    
    return newfunc

if __name__=="__main__":
    import doctest
    doctest.testmod()
    class Test:
        def __init__(self):
            self.value=0
            self.bval = True
            self.optionval = "Maybe"
            self.textval="Matt"
            self._height=5

        def get_test(self):
            print "Getting as", self.value
            return self.value
            
        @slider(getfunc=get_test)
        def test(self, newval):
            """
            Simple example of how to use the slider decorator.
            We decorate the setter function, assuming UI controls will
            change rather than display values.
            
            When this function is called it will automatically update the
            linked slider.
            """
            print "Setting to", newval
            self.value = newval
        
        @slider(getfunc=get_test)
        def test2(self, newval):
            """
            Another slider with the same getfunc. When this gets set it
            calls the test function, so the test slider will update
            automatically.
            
            However, calling test will not update the test2 slider.
            """
            self.test(newval)            
        
        @button
        def button1(self):
            """
            This calls the regular set function, UI elements will get
            updated!
            """
            self.test(50)
            self.boolval(not self.get_bool())
            self.combo("Maybe")
            
        def get_combo(self):
            print "Getting Yes"
            return self.optionval
            
        @combobox(getfunc=get_combo, options=["Yes", "No", "Maybe"])
        def combo(self, t):
            print "setting combo to", t
            self.optionval = t
            
        def get_bool(self):
            return self.bval
            
        @checkbox(getfunc=get_bool)
        def boolval(self, newval):
            print "Setting boolval to", newval
            self.bval = newval
        
        def get_name(self):
            return self.textval
            
        @textbox(getfunc=get_name)
        def name(self, val):
            print "setting name to", val
            self.textval = val
            
        def get_height(self):
            return self._height
            
        @slider(getfunc=get_height)
        @textbox(getfunc=get_height)
        def height(self, val):
            val = float(val)
            self._height=val
            return val  # return a float, 
            
    t=Test()
    from qt_framework import Framework
    import contextlib
    with contextlib.closing(Framework()) as f:
        f.display(t)