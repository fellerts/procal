import sys
from PyQt5 import QtGui, QtCore, QtWidgets, QtWidgets


class BinaryTableItem(QtWidgets.QTableWidgetItem):
    '''
        Dynamic QTableWidgetItem displaying a single bit
    '''
    def __init__(self, index):
        QtWidgets.QTableWidgetItem.__init__(self)

        self.index = index
        self.value = False

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

    def notify_clicked(self):
        # clicked implies pressed became false
        self.is_pressed = False

    def _toggle(self):
        self.value = not self.value
        self.setText(f'{self.value:b}')

        if self.value:
            self.setBackground(QtGui.QColor(240, 200, 200))
        else:
            self.setBackground(QtGui.QColor(255, 255, 255))

    def force_to(self, value):
        self.value = value
        self.setText(f'{self.value:b}')

        if self.value:
            self.setBackground(QtGui.QColor(240, 200, 200))
        else:
            self.setBackground(QtGui.QColor(255, 255, 255))


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
        
        self.init_table_properties()
        self.populate_table()

    def init_table_properties(self):
        
        # we need four rows (2 rows of bits, 2 rows of labels)
        self.setRowCount(4)
        
        # we need 17 columns (16 columns of bits, one spacer column)
        self.setColumnCount(17)
        self.horizontalHeader().setMaximumSectionSize(25)
        
        # register callbacks for various signals emitted by items on mouse interaction
        # allowing user to click/drag select/deselect
        self.itemEntered.connect(self.on_item_entered)
        self.itemClicked.connect(self.on_item_clicked)
        self.itemPressed.connect(self.on_item_pressed)
        
        # set table visual properties
        self.horizontalHeader().setVisible(False)
        self.verticalHeader().setVisible(False)
        self.setFocusPolicy(False)
        self.setShowGrid(False)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.resizeColumnsToContents()
        self.setSizeAdjustPolicy(QtWidgets.QAbstractScrollArea.AdjustToContents)

    def populate_table(self):
        
        # brute-force way of populating the table with clickable bits, labels and spacers
        
        digit_index = 0
        for col in range(17):
            if col == 8:
                self.setItem(2, col, BinaryTableSpacer())
                self.setItem(3, col, BinaryTableSpacer())
            else:

                item = BinaryTableItem(digit_index)
                self.table_elements.append(item)
                self.setItem(3, 16 - col, item)

                item = BinaryTableLegend(digit_index)
                self.setItem(2, 16 - col, item)

                digit_index += 1

        for col in range(17):
            if col == 8:
                self.setItem(0, col, BinaryTableSpacer())
                self.setItem(1, col, BinaryTableSpacer())
            else:

                item = BinaryTableItem(digit_index)
                self.table_elements.append(item)
                self.setItem(1, 16 - col, item)

                item = BinaryTableLegend(digit_index)
                self.setItem(0, 16 - col, item)

                digit_index += 1

    def get_value(self):

        val = 0
        for item in self.table_elements:
            if item.value:
                val += (1 << item.index)
        return val

    def set_value(self, value):
        
        # propagate value
        self._callback(value)
        
        # abort if we cannot display it
        if type(value) != int or value >= 2**32:
            return
            
        # upadte bit field to match value
        for bit in range(32):
            if (1 << bit) & value:
                self.table_elements[bit].force_to(True)
            else:
                self.table_elements[bit].force_to(False)

    def connect(self, callback):
        self.callbacks.append(callback)

    def on_item_entered(self, item):
        
        if not isinstance(item, BinaryTableItem):
            return

        # user entered cell with mouse button down, update item state
        item.notify_entered_while_pressed()
        val = self.get_value()
        self._callback(val)

    def on_item_clicked(self, item):

        if not isinstance(item, BinaryTableItem):
            return

        # user clicked and released in item
        val = self.get_value()
        self._callback(val)

    def on_item_pressed(self, item):

        if not isinstance(item, BinaryTableItem):
            return
        
        # user clicked but has not yet released in item
        item.notify_pressed()
        val = self.get_value()
        self._callback(val)

    def _callback(self, value):
        for cb in self.callbacks:
            cb(value)


class InputLabel(QtWidgets.QLineEdit):
    '''
        Class inheriting QLineEdit for taking user input and evaluating 
        it as python code
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
        except SyntaxError:
            self._callback('Syntax error')
        except Exception:
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
        self._signed = False
        self._result = 0
        # allow user to select text
        self.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)

    def toggle_signed(self, result):
        self._signed = not self._signed
        self.set_result(self._result)

    def set_result(self, result):
        self._result = result
        if type(result) == str:
            self.setText(f'{result}')
        else:
            if self._signed and (result & (1 << 31)):
                negated_result = (result ^ 0xffffffff) + 1
                self.setText(f'0b{result:b} = -{negated_result} = 0x{result:x}')
            else:
                self.setText(f'0b{result:b} = {result} = 0x{result:x}')


class MainWindow(QtWidgets.QMainWindow):

    def __init__(self):
        super().__init__()
        central_widget = QtWidgets.QWidget()
        layout = QtWidgets.QGridLayout()

        # create fields
        input_field = InputLabel()
        binary_view = BinaryView()
        binary_result = ResultField()
        reset_button = QtWidgets.QPushButton('Clear')
        complement_checkbox = QtWidgets.QCheckBox('Two\'s complement')

        # connect input field valid result to binary view update
        input_field.connect(binary_view.set_value)

        # connect binary view update to binary result label
        binary_view.connect(binary_result.set_result)

        # connect reset button to input field reset
        reset_button.clicked.connect(input_field.reset)
        
        # connect Two's complement checkbox to update signedness in binary_result
        complement_checkbox.toggled.connect(binary_result.toggle_signed)

        # arrange items inside layout
        layout.addWidget(reset_button, 0, 0)
        layout.addWidget(input_field, 0, 1)
        layout.addWidget(binary_view, 1, 0, 1, 2)
        layout.addWidget(binary_result, 2, 0, 1, 2)
        layout.addWidget(complement_checkbox, 3, 0)
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)
        
        # initialize input field, this cascades to the binary view 
        # # and reset_button
        input_field.reset()
        input_field.setFocus()
        input_field.selectAll()


if __name__ == "__main__":
    # boilerplate for starting Qt applications
    app = QtWidgets.QApplication(sys.argv)
    main_window = MainWindow()
    main_window.show()
    sys.exit(app.exec_())
