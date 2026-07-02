# tools/geoprocessing.py
import io, os, time
import geopandas as gpd
import pandas as pd
import rasterio
from rasterio.mask import mask as rasterio_mask
from PyQt6.QtWidgets import (
    QApplication, QVBoxLayout, QHBoxLayout, QPushButton,
    QFileDialog, QLabel, QListWidget, QListWidgetItem,
    QDialog, QProgressBar, QLineEdit, QMessageBox
)
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import QSize
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from layers.raster import TIFFLayer
from layers.vector import ShapefileLayer


def buffer_data(main_window):
    dialog = QDialog(main_window)
    dialog.setWindowIcon(QIcon('icons/buffer.png'))
    dialog.setWindowTitle("Buffer")
    layout = QVBoxLayout(dialog)

    list_layout = QHBoxLayout()
    variable_list = QListWidget(dialog)
    list_layout.addWidget(variable_list)
    layout.addLayout(list_layout)

    for layer in main_window.layers:
        item = QListWidgetItem(str(layer))
        item.setData(0, layer)
        variable_list.addItem(item)

    def open_file_dialog():
        layer_path, _ = QFileDialog.getOpenFileName(
            dialog, "Select Shapefile", "", "Shapefiles (*.shp)"
        )
        if layer_path:
            layer = ShapefileLayer(layer_path)
            main_window.layers.append(layer)
            item = QListWidgetItem(str(layer))
            item.setData(0, layer)
            variable_list.addItem(item)

    load_btn = QPushButton(dialog)
    load_btn.setIcon(QIcon('icons/folder.png'))
    load_btn.setIconSize(QSize(25, 25))
    load_btn.clicked.connect(open_file_dialog)
    list_layout.addWidget(load_btn)

    layout.addWidget(QLabel("Distance (metres):"))
    distance = QLineEdit(dialog)
    layout.addWidget(distance)

    btn_layout = QHBoxLayout()
    ok_btn = QPushButton("Ok")
    cancel_btn = QPushButton("Cancel")
    btn_layout.addWidget(ok_btn)
    btn_layout.addWidget(cancel_btn)
    layout.addLayout(btn_layout)
    ok_btn.clicked.connect(dialog.accept)
    cancel_btn.clicked.connect(dialog.reject)

    if dialog.exec() != QDialog.DialogCode.Accepted:
        return

    selected_item = variable_list.currentItem()
    if not selected_item:
        main_window.status_Bar.showMessage("No layer selected.", 5000)
        return

    layer = selected_item.data(0)
    if not layer:
        return

    layer_path = layer.file_path
    layer_name = str(layer)
    buffer_distance = float(distance.text()) if distance.text() else 0.0

    progress_bar = QProgressBar()
    main_window.status_Bar.addPermanentWidget(progress_bar)
    progress_bar.setValue(0)
    QApplication.processEvents()

    try:
        gdf = gpd.read_file(layer_path)

        if gdf.crs is None:
            gdf.set_crs("EPSG:4326", allow_override=True, inplace=True)

        progress_bar.setValue(20)
        QApplication.processEvents()

        gdf = gdf.to_crs(epsg=3857)
        gdf['geometry'] = gdf.geometry.buffer(distance=buffer_distance)
        gdf = gdf.to_crs(epsg=4326)

        progress_bar.setValue(60)
        QApplication.processEvents()

        os.makedirs("data", exist_ok=True)
        file_path = f"data/buffered_{os.path.basename(layer_path)}"
        file_name = os.path.basename(file_path)
        gdf.to_file(file_path)

        progress_bar.setValue(80)
        QApplication.processEvents()

        new_layer = ShapefileLayer(file_path)
        new_layer.add_to_map(main_window.m)
        main_window.layers.append(new_layer)
        main_window.add_layer_checkbox(new_layer, file_name)

        data = io.BytesIO()
        main_window.m.save(data, close_file=False)
        main_window.web_view.setHtml(data.getvalue().decode())

        progress_bar.setValue(100)
        main_window.status_Bar.showMessage(f"{layer_name} buffered successfully", 5000)

    except Exception as e:
        main_window.status_Bar.showMessage(f"Buffer error: {e}", 10000)
    finally:
        main_window.status_Bar.removeWidget(progress_bar)


def clip(main_window):
    dialog = QDialog(main_window)
    dialog.setWindowIcon(QIcon('icons/buffer.png'))
    dialog.setWindowTitle("Clip")
    dialog.resize(500, 300)
    layout = QVBoxLayout(dialog)

    def file_row(label_text, filter_str, save=False):
        layout.addWidget(QLabel(label_text))
        row = QHBoxLayout()
        edit = QLineEdit()
        row.addWidget(edit)
        btn = QPushButton()
        btn.setIcon(QIcon('icons/folder.png'))
        btn.setIconSize(QSize(25, 25))
        if save:
            btn.clicked.connect(lambda: (
                edit.setText(
                    QFileDialog.getSaveFileName(dialog, "Save", "", filter_str)[0]
                )
            ))
        else:
            btn.clicked.connect(lambda: (
                edit.setText(
                    QFileDialog.getOpenFileName(dialog, "Open", "", filter_str)[0]
                )
            ))
        row.addWidget(btn)
        layout.addLayout(row)
        return edit

    input_edit  = file_row("Input Layer:",          "GeoData (*.tif *.tiff *.shp *.nc)")
    mask_edit   = file_row("Mask Shapefile:",        "Shapefile (*.shp)")
    output_edit = file_row("Output Path:",           "GeoData (*.tif *.tiff *.shp)", save=True)

    btn_layout = QHBoxLayout()
    ok_btn = QPushButton("Ok")
    cancel_btn = QPushButton("Cancel")
    btn_layout.addWidget(ok_btn)
    btn_layout.addWidget(cancel_btn)
    layout.addLayout(btn_layout)
    ok_btn.clicked.connect(dialog.accept)
    cancel_btn.clicked.connect(dialog.reject)

    if dialog.exec() != QDialog.DialogCode.Accepted:
        return

    input_path  = input_edit.text()
    mask_path   = mask_edit.text()
    output_path = output_edit.text()

    if not all([input_path, mask_path, output_path]):
        main_window.status_Bar.showMessage("All fields required.", 5000)
        return

    ext = os.path.splitext(input_path)[1].lower()
    progress_bar = QProgressBar()
    main_window.status_Bar.addPermanentWidget(progress_bar)

    try:
        mask_gdf = gpd.read_file(mask_path)

        if ext in (".tif", ".tiff"):
            with rasterio.open(input_path) as src:
                mask_gdf = mask_gdf.to_crs(src.crs)
                out_image, out_transform = rasterio_mask(
                    src, mask_gdf.geometry, crop=True
                )
                out_meta = src.meta.copy()
                out_meta.update({
                    "height": out_image.shape[1],
                    "width":  out_image.shape[2],
                    "transform": out_transform,
                })
            progress_bar.setValue(70)
            QApplication.processEvents()
            with rasterio.open(output_path, "w", **out_meta) as dest:
                dest.write(out_image)
            layer = TIFFLayer(output_path)

        elif ext == ".shp":
            gdf = gpd.read_file(input_path)
            mask_gdf = mask_gdf.to_crs(gdf.crs)
            clipped = gpd.clip(gdf, mask_gdf)
            clipped.to_file(output_path)
            layer = ShapefileLayer(output_path)

        else:
            main_window.status_Bar.showMessage(
                f"Clip not supported for {ext} files.", 5000
            )
            return

        progress_bar.setValue(90)
        QApplication.processEvents()

        layer.add_to_map(main_window.m)
        main_window.layers.append(layer)
        main_window.add_layer_checkbox(layer, os.path.basename(output_path))

        data = io.BytesIO()
        main_window.m.save(data, close_file=False)
        main_window.web_view.setHtml(data.getvalue().decode())

        progress_bar.setValue(100)
        main_window.status_Bar.showMessage("Clip completed successfully.", 5000)

    except Exception as e:
        main_window.status_Bar.showMessage(f"Clip error: {e}", 10000)
    finally:
        main_window.status_Bar.removeWidget(progress_bar)


def union(main_window):
    dialog = QDialog(main_window)
    dialog.setWindowIcon(QIcon('icons/buffer.png'))
    dialog.setWindowTitle("Union")
    layout = QVBoxLayout(dialog)

    layout.addWidget(QLabel("Select two layers to union:"))
    list1 = QListWidget(dialog)
    list2 = QListWidget(dialog)

    for layer in main_window.layers:
        for lst in (list1, list2):
            item = QListWidgetItem(str(layer))
            item.setData(0, layer)
            lst.addItem(item)

    layout.addWidget(QLabel("Layer 1:"))
    layout.addWidget(list1)
    layout.addWidget(QLabel("Layer 2:"))
    layout.addWidget(list2)

    output_layout = QHBoxLayout()
    output_edit = QLineEdit()
    output_btn = QPushButton()
    output_btn.setIcon(QIcon('icons/folder.png'))
    output_btn.setIconSize(QSize(25, 25))
    output_btn.clicked.connect(lambda: output_edit.setText(
        QFileDialog.getSaveFileName(dialog, "Save Union", "", "Shapefile (*.shp)")[0]
    ))
    output_layout.addWidget(output_edit)
    output_layout.addWidget(output_btn)
    layout.addWidget(QLabel("Output Path:"))
    layout.addLayout(output_layout)

    btn_layout = QHBoxLayout()
    ok_btn = QPushButton("Ok")
    cancel_btn = QPushButton("Cancel")
    btn_layout.addWidget(ok_btn)
    btn_layout.addWidget(cancel_btn)
    layout.addLayout(btn_layout)
    ok_btn.clicked.connect(dialog.accept)
    cancel_btn.clicked.connect(dialog.reject)

    if dialog.exec() != QDialog.DialogCode.Accepted:
        return

    item1 = list1.currentItem()
    item2 = list2.currentItem()
    output_path = output_edit.text()

    if not item1 or not item2 or not output_path:
        main_window.status_Bar.showMessage("Select both layers and an output path.", 5000)
        return

    try:
        gdf1 = gpd.read_file(item1.data(0).file_path)
        gdf2 = gpd.read_file(item2.data(0).file_path)
        gdf2 = gdf2.to_crs(gdf1.crs)

        result = gpd.GeoDataFrame(
            pd.concat([gdf1, gdf2], ignore_index=True), crs=gdf1.crs
        )
        result.to_file(output_path)

        layer = ShapefileLayer(output_path)
        layer.add_to_map(main_window.m)
        main_window.layers.append(layer)
        main_window.add_layer_checkbox(layer, os.path.basename(output_path))

        data = io.BytesIO()
        main_window.m.save(data, close_file=False)
        main_window.web_view.setHtml(data.getvalue().decode())
        main_window.status_Bar.showMessage("Union completed successfully.", 5000)

    except Exception as e:
        main_window.status_Bar.showMessage(f"Union error: {e}", 10000)


def intersect(main_window):
    dialog = QDialog(main_window)
    dialog.setWindowIcon(QIcon('icons/buffer.png'))
    dialog.setWindowTitle("Intersect")
    layout = QVBoxLayout(dialog)

    layout.addWidget(QLabel("Select two layers to intersect:"))
    list1 = QListWidget(dialog)
    list2 = QListWidget(dialog)

    for layer in main_window.layers:
        for lst in (list1, list2):
            item = QListWidgetItem(str(layer))
            item.setData(0, layer)
            lst.addItem(item)

    layout.addWidget(QLabel("Layer 1:"))
    layout.addWidget(list1)
    layout.addWidget(QLabel("Layer 2:"))
    layout.addWidget(list2)

    output_layout = QHBoxLayout()
    output_edit = QLineEdit()
    output_btn = QPushButton()
    output_btn.setIcon(QIcon('icons/folder.png'))
    output_btn.setIconSize(QSize(25, 25))
    output_btn.clicked.connect(lambda: output_edit.setText(
        QFileDialog.getSaveFileName(dialog, "Save Intersect", "", "Shapefile (*.shp)")[0]
    ))
    output_layout.addWidget(output_edit)
    output_layout.addWidget(output_btn)
    layout.addWidget(QLabel("Output Path:"))
    layout.addLayout(output_layout)

    figure = Figure()
    canvas = FigureCanvas(figure)
    layout.addWidget(canvas, stretch=1)

    btn_layout = QHBoxLayout()
    ok_btn = QPushButton("Ok")
    cancel_btn = QPushButton("Cancel")
    btn_layout.addWidget(ok_btn)
    btn_layout.addWidget(cancel_btn)
    layout.addLayout(btn_layout)
    ok_btn.clicked.connect(dialog.accept)
    cancel_btn.clicked.connect(dialog.reject)

    if dialog.exec() != QDialog.DialogCode.Accepted:
        return

    item1 = list1.currentItem()
    item2 = list2.currentItem()
    output_path = output_edit.text()

    if not item1 or not item2 or not output_path:
        main_window.status_Bar.showMessage("Select both layers and an output path.", 5000)
        return

    try:
        gdf1 = gpd.read_file(item1.data(0).file_path)
        gdf2 = gpd.read_file(item2.data(0).file_path)
        gdf2 = gdf2.to_crs(gdf1.crs)

        result = gpd.overlay(gdf1, gdf2, how='intersection')
        result.to_file(output_path)

        ax = figure.add_subplot(111)
        result.plot(ax=ax, color='red')
        canvas.draw()

        layer = ShapefileLayer(output_path)
        layer.add_to_map(main_window.m)
        main_window.layers.append(layer)
        main_window.add_layer_checkbox(layer, os.path.basename(output_path))

        data = io.BytesIO()
        main_window.m.save(data, close_file=False)
        main_window.web_view.setHtml(data.getvalue().decode())
        main_window.status_Bar.showMessage("Intersect completed successfully.", 5000)

    except Exception as e:
        main_window.status_Bar.showMessage(f"Intersect error: {e}", 10000)


def extract_by_mask(main_window):
    dialog = QDialog(main_window)
    dialog.setWindowTitle("Extract by Mask")
    dialog.resize(500, 300)
    layout = QVBoxLayout(dialog)

    def file_row(label_text, filter_str, save=False):
        layout.addWidget(QLabel(label_text))
        row = QHBoxLayout()
        edit = QLineEdit()
        row.addWidget(edit)
        btn = QPushButton()
        btn.setIcon(QIcon('icons/folder.png'))
        btn.setIconSize(QSize(25, 25))
        if save:
            btn.clicked.connect(lambda: edit.setText(
                QFileDialog.getSaveFileName(dialog, "Save", "", filter_str)[0]
            ))
        else:
            btn.clicked.connect(lambda: edit.setText(
                QFileDialog.getOpenFileName(dialog, "Open", "", filter_str)[0]
            ))
        row.addWidget(btn)
        layout.addLayout(row)
        return edit

    raster_edit = file_row("Input Raster:",     "GeoTIFF (*.tif)")
    mask_edit   = file_row("Mask Shapefile:",   "Shapefile (*.shp)")
    output_edit = file_row("Output Raster:",    "GeoTIFF (*.tif)", save=True)

    btn_layout = QHBoxLayout()
    ok_btn = QPushButton("Ok")
    cancel_btn = QPushButton("Cancel")
    btn_layout.addWidget(ok_btn)
    btn_layout.addWidget(cancel_btn)
    layout.addLayout(btn_layout)
    ok_btn.clicked.connect(dialog.accept)
    cancel_btn.clicked.connect(dialog.reject)

    if dialog.exec() != QDialog.DialogCode.Accepted:
        return

    raster_path = raster_edit.text()
    mask_path   = mask_edit.text()
    output_path = output_edit.text()

    if not all([raster_path, mask_path, output_path]):
        main_window.status_Bar.showMessage("All fields are required.", 5000)
        return

    progress_bar = QProgressBar()
    main_window.status_Bar.addPermanentWidget(progress_bar)
    progress_bar.setValue(0)

    try:
        mask_gdf = gpd.read_file(mask_path)

        with rasterio.open(raster_path) as src:
            mask_gdf = mask_gdf.to_crs(src.crs)
            out_image, out_transform = rasterio_mask(src, mask_gdf.geometry, crop=True)
            out_meta = src.meta.copy()
            out_meta.update({
                "height":    out_image.shape[1],
                "width":     out_image.shape[2],
                "transform": out_transform,
            })

        progress_bar.setValue(60)
        QApplication.processEvents()

        with rasterio.open(output_path, "w", **out_meta) as dest:
            dest.write(out_image)

        progress_bar.setValue(90)
        QApplication.processEvents()

        layer = TIFFLayer(output_path)
        layer.add_to_map(main_window.m)
        main_window.layers.append(layer)
        main_window.add_layer_checkbox(layer, os.path.basename(output_path))

        data = io.BytesIO()
        main_window.m.save(data, close_file=False)
        main_window.web_view.setHtml(data.getvalue().decode())

        progress_bar.setValue(100)
        main_window.status_Bar.showMessage("Extract by Mask completed successfully.", 5000)

    except Exception as e:
        main_window.status_Bar.showMessage(f"Extract by Mask error: {e}", 10000)
    finally:
        main_window.status_Bar.removeWidget(progress_bar)