import sys
from PyQt5 import QtGui, QtCore, QtWidgets, QtWidgets
import subprocess

# helper function for calculating two's complement at arbitrary bit depth
def twos_complement(onesComplement, nBits):
    if onesComplement & 1 << (nBits - 1) == 0:
        return onesComplement
    else: 
        return ((~onesComplement + 1) & ((1 << nBits) - 1)) * -1

def is_valid_input(string):
    try:
        # try evaluating result
        int(eval(string))
        return True
    except (SyntaxError, Exception):
        return False


class BinaryTableItem(QtWidgets.QTableWidgetItem):
    '''
        Dynamic QTableWidgetItem displaying a single bit
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
        Static non-clickable table element showing an index for BinaryView
    '''
    def __init__(self, index):
        QtWidgets.QTableWidgetItem.__init__(self)
        self.setText(f'{index}')
        self.setTextAlignment(QtCore.Qt.AlignBottom | QtCore.Qt.AlignHCenter)
        self.setFlags(QtCore.Qt.ItemNeverHasChildren)


class BinaryTableSpacer(QtWidgets.QTableWidgetItem):
    '''
        Empty non-clickable table element for BinaryView 
    '''
    def __init__(self):
        QtWidgets.QTableWidgetItem.__init__(self)
        self.setText(' ')
        self.setFlags(QtCore.Qt.ItemIsEnabled)


class BinaryView(QtWidgets.QTableWidget):
    '''
        Class inheriting QTableWidget for creating and populating a table containing
        BinaryTableItem, BinaryTableLegend, BinaryTableSpacer elements
    '''
    def __init__(self):
        QtWidgets.QTableWidget.__init__(self)

        self.callbacks = []
        self.table_elements = []
        
        self.width = 16
        self.spacers = int(self.width / 8 - 1)
        self.n_cols = self.width + self.spacers
        
        self.init_table_properties()
        self.populate_table()
        
        self.previously_clicked_cell = None
        
        
    def init_table_properties(self):
        
        # we need four rows (2 rows of bits, 2 rows of labels)
        self.setRowCount(4)
        
        # we need 17 columns (16 columns of bits, one spacer column)
        self.setColumnCount(self.n_cols)
        self.horizontalHeader().setMaximumSectionSize(25)
        
        # register callback for mouse event (cell entered while mouse pressed)
        self.itemEntered.connect(self.on_item_entered)
        
        # set table visual properties
        self.horizontalHeader().setVisible(False)
        self.verticalHeader().setVisible(False)
        self.setFocusPolicy(False)
        self.setShowGrid(False)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setSizeAdjustPolicy(QtWidgets.QAbstractScrollArea.AdjustToContents)
        self.resizeColumnsToContents()

    def populate_table(self):
        
        # brute-force way of populating the table with clickable bits, labels and spacers
        digit_index = 0
        for col in range(self.n_cols):
            
            reverse_index = self.n_cols - 1 - col
            
            if col == 8 or col == 17 or col == 26:
                self.setItem(2, reverse_index, BinaryTableSpacer())
                self.setItem(3, reverse_index, BinaryTableSpacer())
                print(f'col {col} is spacer')
            else:
                item = BinaryTableItem(digit_index)
                self.table_elements.append(item)
                self.setItem(3, reverse_index, item)

                item = BinaryTableLegend(digit_index)
                self.setItem(2, reverse_index, item)

                print(f'col {col} has index {digit_index}, true col {reverse_index}')
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

    def get_value(self):
        val = 0
        for item in self.table_elements:
            if item.value:
                val += (1 << item.index)
        return val

    def set_value(self, value):
        
        # reset bit limits (if previous val was neg)
        for bit in self.table_elements:
            bit.set_is_bit_limit(False)
        
        # propagate value
        self._callback(value)
        
        # sanity check: abort if we cannot display it
        if type(value) != int or value >= 2**32:
            return
            
        if value < 0:
            self.table_elements[-1].set_is_bit_limit(True)
            
        # upadte bit field to match value
        for bit in range(32):
            if (1 << bit) & value:
                self.table_elements[bit].force_to(True)
            else:
                self.table_elements[bit].force_to(False)

    def connect(self, callback):
        self.callbacks.append(callback)
        
    def set_new_bit_limit_cell(self, new_cell):
        
        # update all bits
        for bit in self.table_elements:
            if bit == new_cell:
                # toggle whether the bit that was clicked is the new
                # bit limit
                bit.toggle_is_bit_limit()
            else:
                # tell all the other bits that they are not bit limit
                bit.set_is_bit_limit(False)
                
        # user clicked but has not yet released in item
        val = self.get_value()
        self._callback(val)
        
    def mousePressEvent(self, event):
        # using mousePressEvent instead of itemClicked so we can differentiate right/left clicks
        cell = self.itemAt(event.pos())
        
        if not isinstance(cell, BinaryTableItem):
            # ignore clicks in spacer and legend cells
            return
            
        if event.button() == QtCore.Qt.LeftButton:
            cell._toggle()
            self.previously_clicked_cell = cell
            val = self.get_value()
            self._callback(val)
        elif event.button() == QtCore.Qt.RightButton:
            self.previously_clicked_cell = cell
            self.set_new_bit_limit_cell(cell)
        
    def on_item_entered(self, item):
        
        if not isinstance(item, BinaryTableItem):
            return
            
        # avoid double-toggling
        if item == self.previously_clicked_cell:
            return
            
        # user entered cell with mouse button down, update item state
        item.notify_entered_while_pressed()
        val = self.get_value()
        self._callback(val)

        
    def get_bit_limit(self):
        limit = None
        
        for bit in self.table_elements:
            if bit.is_bit_limit:
                limit = bit.index + 1
        
        return limit

    def _callback(self, value):
        
        bit_limit = self.get_bit_limit()
        
        for cb in self.callbacks:
            if bit_limit is not None:
                cb(value, True, bit_limit)
            else:
                cb(value, False)


class InputLabel(QtWidgets.QLineEdit):
    '''
        Class inheriting QLineEdit for taking user input and evaluating 
        it as python code, propagating the result if it can be cast to int
    '''
    def __init__(self):
        QtWidgets.QLineEdit.__init__(self)
        self.setAlignment(QtCore.Qt.AlignRight)
        self.returnPressed.connect(self._on_changed)
        self.callbacks = []

    def connect(self, callback):
        self.callbacks.append(callback)

    def reset(self):
        self.setText('0')
        self._callback(0)
        
    def force_to(self, value):
        self.setText(value)
        self._on_changed()

    def _callback(self, value):
        for cb in self.callbacks:
            cb(value)

    def _on_changed(self):

        try:
            # evaluate input and try casting result to int
            res = int(eval(self.text()))
            if res >= 2**32:
                self._callback('Out of 32 bit range')
            else:
                self._callback(res)
        
        # int() cast will fail is result is not integer, report "syntax error"
        except (SyntaxError, Exception):
            self._callback('Syntax error')

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
        
        # allow user to select text
        self.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)

    def set_result(self, result, is_signed=False, bit_depth=None):
        
        self.result = result
        
        if type(result) == str:
            # display string results immediately
            self.setText(f'{result}')
        else:
            if is_signed:
                as_signed = twos_complement(result, bit_depth)
                self.setText(f'0b{result:b} = {as_signed} = 0x{result:x}')
            else:
                self.setText(f'0b{result:b} = {result} = 0x{result:x}')
        
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
        binary_view = BinaryView()
        binary_result = ResultField()
        reset_button = QtWidgets.QPushButton('Clear')
        
        # connect input field valid result to binary view update
        self.input_field.connect(binary_view.set_value)

        # connect binary view update to binary result label
        binary_view.connect(binary_result.set_result)

        # connect reset button to input field reset
        reset_button.clicked.connect(self.input_field.reset)
        
        # place widgets in layouts
        self.inputLayout.addWidget(reset_button)
        self.inputLayout.addWidget(self.input_field)
        self.resultLayout.addWidget(binary_result)
        self.layout.addLayout(self.inputLayout)
        self.layout.addWidget(binary_view)
        self.layout.addLayout(self.resultLayout)
        
        # add layout to the central widget
        self.central_widget.setLayout(self.layout)
        self.setCentralWidget(self.central_widget)
        
        # initialize input field, this cascades to the binary view 
        # and reset_button
        self.input_field.reset()
        self.input_field.setFocus()
        self.input_field.selectAll()
        
        # don't allow resizing of window
        self.setFixedSize(self.central_widget.sizeHint())
        
        # create timer for polling xsel to get selected text
        self.timer = QtCore.QTimer()
        self.timer.setInterval(50)
        self.timer.timeout.connect(self.poll_selected_text)
        self.previously_selected_text = None
        
        self.installEventFilter(self)
        
    def eventFilter(self, obj, event):
        
        if event.type() == QtCore.QEvent.WindowDeactivate:
            # start selection polling timer when window loses focus
            self.timer.start()
            
        elif event.type() == QtCore.QEvent.WindowActivate:
            # stop selection polling timer when window gains focus
            self.timer.stop()
            
        return False
            
    def poll_selected_text(self):
        
        try:
            currently_selected = subprocess.check_output('xsel', timeout=1).decode()
        except FileNotFoundError:
            # guard against xsel not being installed
            self.timer.stop()
            return
        except subprocess.TimeoutExpired:
            # sometimes xsel hangs -- can happen when selected text is inside procal
            return
        
        # ignore multi-line selections
        if '\n' in currently_selected or '\r' in currently_selected:
            return
            
        # ignore zero-length selections
        if len(currently_selected) == 0:
            return
            
        # validate currently selected text
        if not is_valid_input(currently_selected):
            return
            
        # make sure current selection differs from previously selected text
        if currently_selected != self.previously_selected_text:
            self.input_field.force_to(currently_selected)
            self.previously_selected_text = currently_selected

if __name__ == "__main__":
    # boilerplate for starting Qt applications
    app = QtWidgets.QApplication(sys.argv)
    main_window = MainWindow()
    main_window.show()
    sys.exit(app.exec_())
