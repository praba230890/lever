import re
from rpython.rlib.objectmodel import compute_hash, specialize, always_inline
import space

class Object:
    _immutable_fields_ = ['interface', 'custom_interface', 'flag', 'number', 'value', 'contents', 'data', 'string[*]', 'iterator', 'arity', 'methods', 'default', 'cells']
    __slots__ = []
    __attrs__ = []
    # The metaclass here takes care every object will get an interface.
    # So programmer doesn't need to do that.
    class __metaclass__(type):
        def __init__(cls, name, bases, dict):
            if name not in ('Object', 'Interface') and 'interface' not in dict:
                cls.interface = Interface(
                    parent = cls.__bases__[0].interface,
                    name = re.sub("(.)([A-Z]+)", r"\1_\2", name).lower().decode('utf-8'))
                if re.match("^L[A-Z]", name):
                    cls.interface.name = name[1:].decode('utf-8')

    def call(self, argv):
        raise space.unwind(space.LTypeError(u"cannot call " + self.repr()))

    def getitem(self, index):
        raise space.unwind(space.LKeyError(self, index))

    def setitem(self, index, value):
        raise space.unwind(space.LKeyError(self, index))

    def iter(self):
        raise space.unwind(space.LTypeError(u"cannot iterate " + self.repr()))

    def listattr(self):
        listing = []
        for name in self.__class__.interface.methods:
            listing.append(space.String(name))
        return listing

    def getattr(self, index):
        try:
            return BoundMethod(self, index, self.__class__.interface.methods[index])
        except KeyError as e:
            raise space.unwind(space.LAttributeError(self, index))

    def setattr(self, index, value):
        raise space.unwind(space.LAttributeError(self, index))

    def callattr(self, name, argv):
        return self.getattr(name).call(argv)

    def contains(self, obj):
        raise space.unwind(space.LTypeError(u"%s cannot contain" % self.repr()))

    def repr(self):
        return u"<%s>" % space.get_interface(self).name

    def hash(self):
        return compute_hash(self)

    def eq(self, other):
        return self is other

    @classmethod
    def instantiator(cls, fn):
        def _instantiate_b_(interface, argv):
            return fn(argv)
        cls.interface.instantiate = _instantiate_b_
        return fn

    @classmethod
    def instantiator2(cls, decorator):
        def _decorator_(fn):
            fn = decorator(fn)
            def _instantiate_wrapper_(interface, argv):
                return fn(argv)
            cls.interface.instantiate = _instantiate_wrapper_
            return fn
        return _decorator_

    @classmethod
    def builtin_method(cls, fn):
        from builtin import Builtin
        builtin = Builtin(fn)
        cls.interface.methods[builtin.name] = builtin

    @classmethod
    def method(cls, name, decorator):
        def _decarotar_(fn):
            from builtin import Builtin
            builtin = Builtin(decorator(fn), name)
            cls.interface.methods[builtin.name] = builtin
            return fn
        return _decarotar_

class Interface(Object):
    _immutable_fields_ = ['instantiate?', 'methods', 'doc']
    # Should add possibility to freeze the interface?
    def __init__(self, parent, name):
        assert isinstance(name, unicode)
        self.parent = parent # TODO: make this matter for custom objects.
        self.name = name
        self.instantiate = None
        self.methods = {}
        if parent is not None:
            self.methods.update(parent.methods)
        self.doc = None

    def call(self, argv):
        if self.instantiate is None:
            if self.name == u'null':
                raise space.unwind(space.LTypeError(u"cannot call null"))
            raise space.unwind(space.LTypeError(u"cannot instantiate " + self.name))
        return self.instantiate(self, argv)

    def repr(self):
        return self.name

    def getattr(self, name):
        if name == u"doc":
            return null if self.doc is None else self.doc
        try:
            return self.__class__.interface.methods[name]
        except KeyError as e:
            return Object.getattr(self, name)

    def setattr(self, name, value):
        if name == u"doc":
            self.doc = value
            return null
        else:
            return Object.setattr(self, name, value)

    def listattr(self):
        listing = Object.listattr(self)
        listing.append(space.String(u"doc"))
        for methodname in self.methods:
            listing.append(space.String(methodname))
        return listing

Interface.interface = Interface(None, u"interface")
Interface.interface.parent = Interface.interface

null = Interface(None, u"null")
null.interface = null
null.parent = null

Object.interface = Interface(null, u"object")

class BoundMethod(Object):
    def __init__(self, obj, name, methodfn):
        self.obj = obj
        self.name = name
        self.methodfn = methodfn

    def call(self, argv):
        argv.insert(0, self.obj)
        return self.methodfn.call(argv)

    def getattr(self, name):
        return self.methodfn.getattr(name)

    def setattr(self, name, value):
        return self.methodfn.setattr(name, value)

    def listattr(self):
        return self.methodfn.listattr()

    def repr(self):
        return u"%s.%s" % (self.obj.repr(), self.name)

# Notice that cast != instantiation.
# The distinction is very important.
cast_methods = {}
def cast_for(cls):
    def _cast_decorator_(x):
        cast_methods[cls] = x
        return x
    return _cast_decorator_

# Cast didn't appear to handle well as a class method, so I made this
# convenient table construct that uses default handling when conversion
# is not available.

# User objects will not have access to implement this method of casting. 
# Userspace casting will be treated as separate problem.

# TODO: frame entry association could be "cool" here. So you would know
#       where a cast attempt failed.
@always_inline
@specialize.arg(1, 2)
def cast(x, cls, info=u"something"):
    if isinstance(x, cls): # This here means that cast won't change object
        return x           # if it is already correct type.
    try:
        fn = cast_methods[cls]
    except KeyError as _:
        raise space.unwind(space.LTypeError(u"expected %s is %s, got %s" % (
            info, cls.interface.name, x.repr())))
    res = fn(x)
    if isinstance(res, cls):
        return res
    # TODO: Consider alternative ways to say it. :)
    raise space.unwind(space.LTypeError(u"implicit conversion of %s at %s into %s returned %s" % (
        x.repr(), info, cls.interface.name, res.repr())))

# Variation of cast that accepts a null value and translates it to None.
@always_inline
@specialize.arg(1, 2)
def cast_n(x, cls, info=u"something"):
    if x is null:
        return None
    return cast(x, cls, info)
