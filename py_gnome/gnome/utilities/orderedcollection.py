

class OrderedCollection(object):

    '''
    Generalized Container for a set of objects of a particular type which
    preserves the order of insertion and supports replacement of not only
    an object in the list, but the key/id that references it. (a normal
    OrderedDict can't do this)
    - The order of insertion is preserved.
    - Objects are accessed by id, as if in a dictionary.
    - Objects can be replaced in order.  The objects will be referenced 
      by a new id, and still be in the correct order.
      
    '''

    def __init__(self, elems=None, dtype=None):
        if elems and not isinstance(elems, list):
            raise TypeError('%s: needs a list of objects'
                            % self.__class__.__name__)
        if not elems:
            elems = []

        if not dtype and len(elems) == 0:
            raise TypeError('%s: specify a data type if list is empty'
                            % self.__class__.__name__)
        elif not dtype:
            self.dtype = type(elems[0])
        else:
            self.dtype = dtype

        if not all([isinstance(e, self.dtype) for e in elems]):
            raise TypeError('%s: needs a list of %s'
                            % (self.__class__.__name__, self.dtype))

        # a bunch of Gnome classes have an id property defined, which we will prefer
        # otherwise, we just take the id(e) value
        # NOTE: we stringify the e.id value since it could be of a type that is hard to reference as a key

        self._index = dict([((str(e.id) if hasattr(e, 'id'
                           ) else id(e)), idx) for (idx, e) in
                           enumerate(elems)])
        self._elems = elems[:]
        self.callbacks = {}

    def get(self, ident):
        return self._elems[self._index[ident]]

    def add(self, elem):
        ''' Add an object to the collection '''

        if isinstance(elem, self.dtype):
            if hasattr(elem, 'id'):

                # a bunch of Gnome classes have an id property defined, which we will prefer.
                # NOTE: the e.id value is stringified since the key has been also.

                l__id = str(elem.id)
            else:
                l__id = id(elem)
            if l__id not in self._index.keys():
                self._index[l__id] = len(self._elems)
                self._elems.append(elem)
                self.fire_event('add', elem)  # fire add event only if elem is not already in the list
        elif isinstance(elem, list) and all([isinstance(e, self.dtype)
                for e in elem]):

            for e in elem:
                self.add(e)  # this will call self.fire_event when the object is added to OC
        else:
            raise TypeError('%s: expected %s, got %s'
                            % (self.__class__.__name__, self.dtype,
                            type(elem)))

    def remove(self, ident):
        ''' Remove an object from the collection '''

        self.fire_event('remove', self[ident])  # fire remove event before removing from collection
        if ident in self._index:
            self._elems[self._index[ident]] = None
            del self._index[ident]
        else:
            self._elems[self._index[str(ident)]] = None
            del self._index[str(ident)]

    def replace(self, ident, new_elem):
        if not isinstance(new_elem, self.dtype):
            raise TypeError('%s: expected %s, got %s'
                            % (self.__class__.__name__, self.dtype,
                            type(new_elem)))

        if ident in self._index.keys():
            l__key = ident
        elif str(ident) in self._index.keys():
            l__key = str(ident)
        else:
            self.add(new_elem)
            return

        # we have an existing object

        idx = self._index[l__key]
        del self._index[l__key]
        if hasattr(new_elem, 'id'):

            # a bunch of Gnome classes have an id property defined, which we will prefer
            # NOTE: the e.id value is stringified since the key has been also.

            self._index[str(new_elem.id)] = idx
        else:
            self._index[id(new_elem)] = idx
        self._elems[idx] = new_elem

        self.fire_event('replace', new_elem)  # returns the newly added object

    def index(self, ident, renumber=True):
        idx = self._index[ident]
        if renumber:
            return sorted(self._index.values()).index(idx)
        else:
            return idx

    def __len__(self):
        return len(self._index.keys())

    def __iter__(self):
        for i in sorted(self._index.values()):
            yield self._elems[i]

    def __contains__(self, ident):
        return ident in self._index

    def __getitem__(self, ident):
        return self.get(ident)

    def __setitem__(self, ident, new_elem):
        self.replace(ident, new_elem)

    def __delitem__(self, ident):
        self.remove(ident)

    def __iadd__(self, rop):
        self.add(rop)
        return self

    def __str__(self):
        itemlist = sorted(self._index.items(), key=lambda x: x[1])  # order by position in list
        itemlist = [(k, self._elems[v]) for (k, v) in itemlist]  # reference the value in list
        if len(itemlist) > 6:  # should we abbreviate the list?
            strlist = ['\t%s: %s,' % i for i in itemlist[:2]]
            strlist += ('\t...', '\t...')
            strlist += ['\t%s: %s,' % i for i in itemlist[-2:]]
        else:
            strlist = ['\t%s: %s,' % i for i in itemlist]
        return '''%s({
%s
})''' % (self.__class__.__name__,
                                   '\n'.join(strlist))

    def __repr__(self):
        return self.__str__()

    def __eq__(self, other):
        """ Equality of two ordered collections """

        if not isinstance(other, OrderedCollection):
            return False

        if len(self) != len(other):
            return False

        for oc in zip(self, other):
            if oc[0] != oc[1]:
                return False

        return True

    def __ne__(self, other):
        """ Check if two ordered collections are not equal (!= opertor)"""

        if self == other:
            return False
        else:
            return True

    def to_dict(self):
        """
        method takes the instance of ordered collection and outputs a dict with 
        two fields:
            dtype: associated dtype for each object in the order in which it is added
            id : contains list of IDs of each object in the order in which it is added
            
        This method assumes object has an ID
        """

        dict_ = {'dtype': self.dtype, 'id_list': []}

        for obj in self:
            obj_type = \
                '{0.__module__}.{0.__class__.__name__}'.format(obj)
            dict_['id_list'].append((obj_type, obj.id))

        return dict_

    def register_callback(self, callback, events=('add', 'remove',
                          'replace')):
        if not isinstance(events, (list, tuple)):
            events = (events, )

        for event in events:
            if event not in ('add', 'remove', 'replace'):
                raise ValueError("Events must be either ('add','remove','replace'). {0} is not supported".format(event))

        self.callbacks[callback] = events

    def fire_event(self, event, obj_):
        for (callback, reg_event) in self.callbacks.items():
            if event in reg_event:
                callback(obj_)  # this should be all that is required


