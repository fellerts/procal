from PyQt5 import QtGui, QtCore, QtWidgets, QtWidgets

import struct


def to_float(value):
    # interpret the bits of value as IEEE 754 floating point number
    # see https://en.wikipedia.org/wiki/IEEE_754

    literal = 0
    string = ''

    sign = (value >> 31) & 0x01
    exponent = (value >> 23) & 0xFF
    fraction = (value & 0x7FFFFF)
    
    literal = (-1) ** (sign)
    string += f'{(-1) ** (sign)}*'
    
    if exponent == 0xFF:
        # nan/inf
        if fraction == 0x00:
            if sign == 0x01:
                literal = float('-inf')
            else:
                literal = float('+inf')
        else:
            literal = float('nan')
        
        string = ''
            
    elif exponent == 0x00:
        # subnormal number
        literal *= 2 ** (-126) * fraction / (2**23)
        string += f'2^(-126)*({fraction / (2**23)})'
        
    else:
        # normal number
        literal *= 2 ** ((exponent) - 127)
        literal *= (1 + fraction / (2**23))
        
        string += f'2^({exponent} - 127)*'
        string += f'({1 + fraction / (2**23)})'
    
    return literal, string


class BinaryTableItem(QtWidgets.QTableWidgetItem):
    '''
        Clickable QTableWidgetItem displaying a single bit
    '''
    def __init__(self, index):
        QtWidgets.QTableWidgetItem.__init__(self)

        self.index = index
        self.value = False
        self.is_bit_limit = False

        # mouse button down
        self.is_pressed = False

        self.setText(f'{self.value:b}')
        self.setFont(QtGui.QFont('monospace', 10))
        self.setTextAlignment(QtCore.Qt.AlignCenter)
        self.setFlags(QtCore.Qt.ItemIsEnabled)

    def notify_pressed(self):
        self.is_pressed = True
        self._toggle()

    def notify_entered_while_pressed(self):
        # but in qt: when mouse is pressed down inside a cell, notify_pressed triggers
        # and then notify_entered_while_pressed when mouse starts moving. However if
        # notify_pressed did not trigger, we are entering this cell from elsewhere.
        if not self.is_pressed:
            self._toggle()
        
        # this bug only happens once, so we can clear the pressed flag here.
        self.is_pressed = False

    def set_is_bit_limit(self, is_bit_limit):
        self.is_bit_limit = is_bit_limit
        self._update_color()

    def toggle_is_bit_limit(self):
        self.is_bit_limit = not self.is_bit_limit
        self._update_color()

    def _toggle(self):
        self.value = not self.value
        self.setText(f'{self.value:b}')
        self._update_color()

    def _update_color(self):
        if self.is_bit_limit:
            self.setBackground(QtGui.QColor(200, 240, 200))
        elif self.value:
            self.setBackground(QtGui.QColor(240, 200, 200))
        else:
            self.setBackground(QtGui.QColor(255, 255, 255))

    def force_to(self, value):
        self.value = value
        self.setText(f'{self.value:b}')

        self._update_color()


class BinaryTableLegend(QtWidgets.QTableWidgetItem):
    '''
        Non-clickable table element showing an index for BinaryView
    '''
    def __init__(self, index):
        QtWidgets.QTableWidgetItem.__init__(self)
        self.setText(f'{index}')
        self.setTextAlignment(QtCore.Qt.AlignBottom | QtCore.Qt.AlignHCenter)
        self.setFlags(QtCore.Qt.ItemNeverHasChildren)
        self.setFont(QtGui.QFont('monospace', 10))


class BinaryTableSpacer(QtWidgets.QTableWidgetItem):
    '''
        Empty non-clickable table element for BinaryView
    '''
    def __init__(self):
        QtWidgets.QTableWidgetItem.__init__(self)
        self.setText(' ')
        self.setFlags(QtCore.Qt.ItemIsEnabled)


class BinaryTableLabel(QtWidgets.QTableWidgetItem):
    '''
        Empty non-clickable table element for BinaryView
    '''

    def __init__(self, label):
        QtWidgets.QTableWidgetItem.__init__(self)
        self.setText(label)
        self.setFlags(QtCore.Qt.ItemIsEnabled)
        self.setTextAlignment(QtCore.Qt.AlignTop)
        self.setFont(QtGui.QFont('monospace', 10))

class BinaryView(QtWidgets.QTableWidget):
    '''
        Class inheriting QTableWidget for creating and populating a table containing
        BinaryTableItem, BinaryTableLegend, BinaryTableSpacer elements
    '''
    
    MODE_FLOAT = 1
    MODE_INT = 2

    def __init__(self, n_bits=32, mode=MODE_INT):
        QtWidgets.QTableWidget.__init__(self)

        self.callbacks = []
        self.table_elements = []
        self.mode = mode
        self.error_message = None
        self.previously_clicked_cell = None
        
        # register callback for mouse event (cell entered while mouse pressed)
        self.itemEntered.connect(self._on_item_entered)
        self.set_new_bit_width(n_bits)
        
    def new_mode(self, mode):
        if mode == self.mode:
            return
            
        self.mode = mode
        self.set_new_bit_width(32)
     
    def get_value(self):

        as_uint = 0

        # grab unsigned value
        for item in self.table_elements:
            if item.value:
                as_uint += (1 << item.index)

        # grab signed value
        bit_limit = self.get_sign_bit_index()
        if bit_limit is not None:
            as_signed = self._twos_complement(as_uint, bit_limit + 1)
        else:
            as_signed = None

        if self.mode == self.MODE_INT:
            return as_uint, as_signed, None
        elif self.mode == self.MODE_FLOAT:
            as_float, _ = to_float(as_uint)
            return as_uint, as_signed, as_float

    def set_value(self, value):
        
        if type(value) == str:
            # string input interpreted as error message
            self.error_message = value
            self._callback()
            return
        
        if self.mode == self.MODE_INT and value.is_integer() is not True:
            # got a float while in int mode, warn user
            self.error_message = '\nCannot represent float in int mode'
            self._callback()
            return
            
        if self.mode == self.MODE_FLOAT:
            # pack and unpack to get integer representation of hex
            tmp = struct.pack('>f', value)
            value = int(tmp.hex(), 16)
            
        # reset bit limits (if previous val was neg)
        for bit in self.table_elements:
            bit.set_is_bit_limit(False)
            
        value = int(value)
        
        # sanity check: abort if we cannot display it
        if value >= 2**self.n_bits:
            self.error_message = f'Out of {self.n_bits} bit range'
            self._callback()
            return
        elif value < 0:
            self.table_elements[-1].set_is_bit_limit(True)

        # upadte bit field to match value
        for bit in range(self.n_bits):
            if (1 << bit) & value:
                self.table_elements[bit].force_to(True)
            else:
                self.table_elements[bit].force_to(False)

        self._callback()
        
    def connect(self, callback):
        self.callbacks.append(callback)

    def set_sign_bit_index(self, index):

        # update all bits
        for bit in self.table_elements:
            if bit.index == index:
                # toggle whether the bit that was clicked is the new
                # bit limit
                bit.toggle_is_bit_limit()
            else:
                # tell all the other bits that they are not bit limit
                bit.set_is_bit_limit(False)

        # user clicked but has not yet released in item
        self._callback()

    def mousePressEvent(self, event):
        # using mousePressEvent instead of itemClicked so we can differentiate right/left clicks
        cell = self.itemAt(event.pos())

        if not isinstance(cell, BinaryTableItem):
            # ignore clicks in spacer and legend cells
            return

        if event.button() == QtCore.Qt.LeftButton:
            # left button toggles bits on/off
            cell._toggle()
            self.previously_clicked_cell = cell
            self._callback()
        elif event.button() == QtCore.Qt.RightButton:
            # right button sets sign bit if we are in int mode
            if self.mode == self.MODE_INT:
                self.previously_clicked_cell = cell
                self.set_sign_bit_index(cell.index)
                
   
    def set_new_bit_width(self, n_bits):
        if n_bits not in [32, 64]:
            print("invalid number of bits requested, choose from 32, 64")
            return
            
        # delete table elements if they exist
        while self.rowCount() > 0:
            self.removeRow(0)
        self.table_elements = []

        self.n_bits = n_bits

        # helper variables for constructing table
        self.width = int(n_bits / 2)
        self.n_spacers = int(self.width / 8 - 1)
        self.n_cols = self.width + self.n_spacers


        if self.mode == self.MODE_FLOAT:
            self._init_table_properties_float()
            self._populate_table_float()
        elif self.mode == self.MODE_INT:
            self._init_table_properties_int()
            self._populate_table_int()

    def _init_table_properties_float(self):

        self.setRowCount(4)

        # we need 34 columns (32 for bits, 2 for columns)
        self.n_cols = 34
        self.setColumnCount(self.n_cols)
        self.horizontalHeader().setMaximumSectionSize(25)

        # set table visual properties
        self.horizontalHeader().setVisible(False)
        self.verticalHeader().setVisible(False)
        self.setFocusPolicy(False)
        self.setShowGrid(False)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setSizeAdjustPolicy(QtWidgets.QAbstractScrollArea.AdjustToContents)
        self.resizeColumnsToContents()

    def _init_table_properties_int(self):

        # we need four rows (2 rows of bits, 2 rows of labels)
        self.setRowCount(4)

        # we need 17 columns (16 columns of bits, one spacer column)
        self.setColumnCount(self.n_cols)
        self.horizontalHeader().setMaximumSectionSize(25)

        # set table visual properties
        self.horizontalHeader().setVisible(False)
        self.verticalHeader().setVisible(False)
        self.setFocusPolicy(False)
        self.setShowGrid(False)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setSizeAdjustPolicy(QtWidgets.QAbstractScrollArea.AdjustToContents)
        self.resizeColumnsToContents()

    def _populate_table_float(self):

        # brute-force way of populating the table with clickable bits, labels and spacers
        digit_index = 0
        for col in range(self.n_cols):

            reverse_index = self.n_cols - 1 - col

            if col == 32 or col == 23:
                self.setItem(0, reverse_index, BinaryTableSpacer())
                self.setItem(1, reverse_index, BinaryTableSpacer())
            else:
                item = BinaryTableItem(digit_index)
                self.table_elements.append(item)
                self.setItem(1, reverse_index, item)

                item = BinaryTableLegend(digit_index)
                self.setItem(0, reverse_index, item)

                digit_index += 1

        self.setSpan(2, 0,  1, 2)
        self.setSpan(2, 2,  1, 3)
        self.setSpan(2, 11, 1, 3)
        self.setItem(2, 0,  BinaryTableLabel('Sign'))
        self.setItem(2, 2,  BinaryTableLabel('Exponent'))
        self.setItem(2, 11, BinaryTableLabel('Mantissa'))
        
    def _populate_table_int(self):

        # brute-force way of populating the table with clickable bits, labels and spacers
        digit_index = 0
        for col in range(self.n_cols):

            reverse_index = self.n_cols - 1 - col

            if col == 8 or col == 17 or col == 26:
                self.setItem(2, reverse_index, BinaryTableSpacer())
                self.setItem(3, reverse_index, BinaryTableSpacer())
            else:
                item = BinaryTableItem(digit_index)
                self.table_elements.append(item)
                self.setItem(3, reverse_index, item)

                item = BinaryTableLegend(digit_index)
                self.setItem(2, reverse_index, item)

                digit_index += 1

        for col in range(self.n_cols):

            reverse_index = self.n_cols - 1 - col

            if col == 8 or col == 17 or col == 26:
                self.setItem(0, reverse_index, BinaryTableSpacer())
                self.setItem(1, reverse_index, BinaryTableSpacer())
            else:

                item = BinaryTableItem(digit_index)
                self.table_elements.append(item)
                self.setItem(1, reverse_index, item)

                item = BinaryTableLegend(digit_index)
                self.setItem(0, reverse_index, item)

                digit_index += 1


    def _on_item_entered(self, item):
        
        if not isinstance(item, BinaryTableItem):
            return

        # avoid double-toggling
        if item == self.previously_clicked_cell:
            return

        # user entered cell with mouse button down, update item state
        item.notify_entered_while_pressed()
        self._callback()

    def get_sign_bit_index(self):
        limit = None

        for bit in self.table_elements:
            if bit.is_bit_limit:
                limit = bit.index

        return limit

    def _callback(self):

        signed, unsigned, flt = self.get_value()

        for cb in self.callbacks:
            cb(signed, unsigned, flt, self.error_message)
        
        # error message has been propagated, clear it
        self.error_message = None
    
    def _twos_complement(self, onesComplement, nBits):
        # helper function for calculating two's complement at arbitrary bit depth
        if onesComplement & 1 << (nBits - 1) == 0:
            return onesComplement
        else:
            return ((~onesComplement + 1) & ((1 << nBits) - 1)) * -1


class InputLabel(QtWidgets.QLineEdit):
    '''
        Class inheriting QLineEdit for taking user input and evaluating
        it as python code, propagating the result if it can be cast to int
    '''
    def __init__(self):
        QtWidgets.QLineEdit.__init__(self)
        self.setFont(QtGui.QFont('monospace', 10))
        self.setAlignment(QtCore.Qt.AlignRight)
        self.returnPressed.connect(self._on_changed)
        self.callbacks = []

    def connect(self, callback):
        self.callbacks.append(callback)

    def reset(self):
        self.setText('0')
        self._callback(0.0)
        
    def force_evaluation(self):
        self._on_changed()

    def force_to(self, value):
        self.setText(value)
        self._on_changed()
        
    def _callback(self, value):
        for cb in self.callbacks:
            cb(value)

    def _on_changed(self):

        try:
            res = float(eval(self.text()))
            self._callback(res)

        # int() cast will fail is result is not integer, report "syntax error"
        except (SyntaxError, Exception):
            self._callback('\nSyntax error')

        self.setFocus()
        self.selectAll()

class ResultField(QtWidgets.QLabel):
    '''
        Class inheriting QLabel for displaying results
    '''
    def __init__(self):
        QtWidgets.QLabel.__init__(self)
        self.setAlignment(QtCore.Qt.AlignRight)
        self.result = ""
        self.setFont(QtGui.QFont('monospace', 10))

        # allow user to select text
        self.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        self.setSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding, QtWidgets.QSizePolicy.MinimumExpanding)
        self.setFrameStyle(QtWidgets.QFrame.StyledPanel)

    def set_result(self, as_unsigned=None, as_signed=None, as_flt=None, error_message=None):
        
        to_print = ''
        
        if error_message is not None:
            to_print = error_message
        else:
            to_print += f'0b{as_unsigned:b}\n'
            
            if as_flt is not None:
                literal, string = to_float(as_unsigned)
                to_print += string + f' = {literal}' + '\n'
            elif as_signed is not None:
                to_print += f'{as_signed}\n'
            else:
                to_print += f'{as_unsigned}\n'

            to_print += f'0x{as_unsigned:x}'
            
        self.setText(to_print)

class MainWindow(QtWidgets.QMainWindow):

    def __init__(self):
        super().__init__()
        self.central_widget = QtWidgets.QWidget()

        # make layouts to contain widgets
        self.layout = QtWidgets.QVBoxLayout()
        self.inputLayout = QtWidgets.QHBoxLayout()
        self.resultLayout = QtWidgets.QHBoxLayout()

        # create fields
        self.input_field = InputLabel()
        self.binary_view = BinaryView(32, BinaryView.MODE_INT)
        self.binary_result = ResultField()
        reset_button = QtWidgets.QPushButton('Clear')
        
        self.check_64b = QtWidgets.QCheckBox('64 bit')
        self.check_flt = QtWidgets.QCheckBox('float')
        toggles = QtWidgets.QVBoxLayout()
        toggles.addWidget(self.check_64b)
        toggles.addWidget(self.check_flt)
        
        self.check_64b.stateChanged.connect(self.on_64b_clicked)
        self.check_flt.stateChanged.connect(self.on_flt_clicked)
        
        # connect input field valid result to binary view update
        self.input_field.connect(self.binary_view.set_value)

        # connect binary view update to binary result label
        self.binary_view.connect(self.binary_result.set_result)

        # connect reset button to input field reset
        reset_button.clicked.connect(self.input_field.reset)

        # place widgets in layouts
        self.inputLayout.addWidget(reset_button)
        self.inputLayout.addWidget(self.input_field)
        self.resultLayout.addLayout(toggles)
        self.resultLayout.addWidget(self.binary_result)
        
        self.layout.addLayout(self.inputLayout)
        self.layout.addWidget(self.binary_view)
        self.layout.addLayout(self.resultLayout)

        # add layout to the central widget
        self.central_widget.setLayout(self.layout)
        self.setCentralWidget(self.central_widget)

        # initialize input field, this cascades to the binary view
        # and reset_button
        self.input_field.reset()
        self.input_field.setFocus()
        self.input_field.selectAll()

        # set fixed size and save the size so we can return to it if we 
        # expand then contract
        self.contracted_size = self.central_widget.sizeHint()
        self.setFixedSize(self.contracted_size)
        
    def on_64b_clicked(self, state):
        if state > 0:
            # keep current value and sign bit
            curr_val, _, _ = self.binary_view.get_value()
            sign_bit = self.binary_view.get_sign_bit_index()

            # we can always expand from 64 to 32.
            self.binary_view.set_new_bit_width(64)

            # refresh table
            self.binary_view.set_value(float(curr_val))

            self.expanded_size = self.central_widget.sizeHint()
            self.setFixedSize(self.expanded_size)

            # if curr_val was signed, update sign bit as well
            if sign_bit:
                self.binary_view.set_sign_bit_index(sign_bit)

        else:
            # snip all bits > 32 to we can contract
            curr_val, _, _ = self.binary_view.get_value()
            sign_bit = self.binary_view.get_sign_bit_index()
            new_val = curr_val & 0xFFFFFFFF

            # temporarily force table to 0 so the result label fits
            # within a smaller window, this way the window is resized properly
            self.binary_result.set_result(0)

            # resize the table
            self.binary_view.set_new_bit_width(32)

            self.setFixedSize(self.contracted_size)

            # refresh table with the old value sans 32 MBS
            self.binary_view.set_value(float(new_val))

            # if curr_val was signed, update sign bit as well
            if sign_bit:
                if sign_bit < 32:
                    self.binary_view.set_sign_bit_index(sign_bit)
                    
    def on_flt_clicked(self, state):
        if state > 0:
            self.check_64b.setEnabled(False)
            self.binary_view.new_mode(BinaryView.MODE_FLOAT)
            self.contracted_size = self.central_widget.sizeHint()
            self.setFixedSize(self.contracted_size)
            self.input_field.force_evaluation()
        else:
            self.check_64b.setEnabled(True)
            self.check_64b.setChecked(False)
            self.binary_view.new_mode(BinaryView.MODE_INT)
            self.contracted_size = self.central_widget.sizeHint()
            self.setFixedSize(self.contracted_size)
            self.input_field.force_evaluation()
        
    def eventFilter(self, obj, event):

        if event.type() == QtCore.QEvent.WindowDeactivate:
            # start selection polling timer when window loses focus
            self.timer.start()

        elif event.type() == QtCore.QEvent.WindowActivate:
            # stop selection polling timer when window gains focus
            self.timer.stop()

        return False

if __name__ == "__main__":
    # boilerplate for starting Qt applications
    import sys
    app = QtWidgets.QApplication(sys.argv)
    main_window = MainWindow()
    main_window.show()
    sys.exit(app.exec_())