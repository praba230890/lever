from builtin import signature
from interface import Object
from rpython.rlib.objectmodel import compute_hash
from rpython.rlib.unicodedata import unicodedb_6_2_0 as unicodedb
import numbers
import space

class String(Object):
    _immutable_fields_ = ['string[*]']
    __slots__ = ['string']
    def __init__(self, string):
        #assert isinstance(string, unicode)
        self.string = string

    # Not fixing the string here, fix later
    def repr(self):
        return u'"' + self.string + u'"'

    def hash(self):
        return compute_hash(self.string)

    def eq(self, other):
        if isinstance(other, String):
            return self.string == other.string
        return False

    def getattr(self, name):
        if name == u'length':
            return numbers.Integer(len(self.string))
        return Object.getattr(self, name)

    def getitem(self, index):
        if isinstance(index, space.Slice):
            result = []
            start, stop, step = index.clamped(0, len(self.string))
            for i in range(start, stop, step):
                result.append(self.string[i])
            return String(u"".join(result))
        index = space.cast(index, numbers.Integer, u"index not an integer")
        if not 0 <= index.value < len(self.string):
            raise space.unwind(space.LKeyError(self, index))
        return String(self.string[index.value])

    def iter(self):
        return StringIterator(iter(self.string))

@String.builtin_method
@signature(String, Object)
def join(string, seq):
    strings = []
    it = seq.iter()
    while True:
        try:
            x = it.callattr(u"next", [])
            if not isinstance(x, String):
                raise space.OldError(u".join expects strings")
            strings.append(x.string)
        except StopIteration as _:
            break
    return String(string.string.join(strings))

@String.builtin_method
@signature(String)
def is_alpha(string):
    for ch in string.string:
        if not unicodedb.isalpha(ord(ch)):
            return space.false
    return space.true

@String.builtin_method
def is_digit(argv):
    assert len(argv) >= 1
    a0 = argv[0]
    assert isinstance(a0, String)
    base = 10
    if len(argv) >= 2:
        assert len(argv) == 2
        a1 = argv[1]
        assert isinstance(a1, numbers.Integer)
        base = a1.value
    assert 0 <= base <= 36
    for ch in a0.string:
        if not 0 <= as_alphadigit_i(ord(ch)) < base:
            return space.false
    return space.true

def as_alphadigit_i(index):
    if ord('0') <= index <= ord('9'):
        return index - ord('0')
    if ord('A') <= index <= ord('Z'):
        return index - ord('A') + 10
    if ord('a') <= index <= ord('z'):
        return index - ord('a') + 10
    return -1

@String.builtin_method
@signature(String)
def is_space(string):
    for ch in string.string:
        if not unicodedb.isspace(ord(ch)):
            return space.false
    return space.true

@String.method(u"startswith", signature(String, String))
def String_startswith(self, prefix):
    return space.boolean(
        self.string.startswith(prefix.string))

@String.method(u"endswith", signature(String, String))
def String_endswith(self, postfix):
    return space.boolean(
        self.string.endswith(postfix.string))

class StringIterator(Object):
    _immutable_fields_ = ['iterator']
    def __init__(self, iterator):
        self.iterator = iterator

    def iter(self):
        return self
    
@StringIterator.method(u"next", signature(StringIterator))
def StringIterator_next(self):
    return String(self.iterator.next())
