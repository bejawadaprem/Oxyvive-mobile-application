import requests
from kivy.animation import Animation
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.properties import ObjectProperty, StringProperty
from kivy.uix.behaviors import DragBehavior
from kivy.uix.modalview import ModalView
from kivy_garden.mapview import MapView, MapMarker
from kivymd.uix.button import MDFloatingActionButton
from kivymd.uix.dialog import MDDialog
from kivymd.uix.label import MDLabel
from kivymd.uix.list import OneLineIconListItem, IconLeftWidget, OneLineAvatarIconListItem, OneLineAvatarListItem
from kivymd.uix.screen import MDScreen
from opencage.geocoder import OpenCageGeocode
from plyer import gps


class CustomModalView(DragBehavior, ModalView):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.drag_start_y = 0
        self.background = 'rgba(0, 0, 0, 0)'
        self.overlay_color = (0, 0, 0, 0)
        self.size_hint = (None, None)
        self.size = (Window.width, Window.height - dp(150))

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self.drag_start_y = touch.y
            return super().on_touch_down(touch)
        return False

    def on_touch_move(self, touch):
        if self.collide_point(*touch.pos):
            dy = touch.y - self.drag_start_y
            new_height = self.height + dy
            max_height = Window.height - dp(149)
            if new_height < max_height:
                self.height = max(dp(100), new_height)
            self.drag_start_y = touch.y
            return True
        return False

    def on_touch_up(self, touch):
        if self.collide_point(*touch.pos):
            return super().on_touch_up(touch)

    def dismiss_modal(self):
        self.dismiss()


class CustomButtonMap(MDFloatingActionButton):
    def set_size(self, *args):
        self.size = (dp(40), dp(40))


class StaticMapMarker(MapMarker):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.lat = kwargs.get('lat', 0)
        self.lon = kwargs.get('lon', 0)


class CustomMapView(MapView):
    manager = ObjectProperty()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.static_marker = StaticMapMarker(lat=self.lat, lon=self.lon)
        self.add_widget(self.static_marker)
        self.update_marker_position()
        self.geocoder = OpenCageGeocode("7060ef7890c44bb48d75f2d12c66a466")

    def on_map_relocated(self, zoom, coord):
        super().on_map_relocated(zoom, coord)
        self.update_marker_position()
        self.update_text_field()
        screen = self.manager.get_screen("client_location")
        screen.hide_modal_view()

    def update_marker_position(self):
        scatter = self._scatter
        map_source = self.map_source
        zoom = self._zoom
        scale = self._scale

        x = self.width / 2
        y = self.height / 2

        lon = map_source.get_lon(zoom, (x - scatter.x) / scale - self.delta_x)
        lat = map_source.get_lat(zoom, (y - scatter.y) / scale - self.delta_y)

        self.static_marker.lat = lat
        self.static_marker.lon = lon

    def update_text_field(self):
        lat = self.static_marker.lat
        lon = self.static_marker.lon
        self.update_coordinate_text_field(lat, lon)

    def update_coordinate_text_field(self, lat, lon):
        results = self.geocoder.reverse_geocode(lat, lon)
        if results and len(results) > 0:
            formatted_address = results[0].get('formatted')
            if formatted_address:
                screen = self.manager.get_screen("client_location")
                screen.ids.autocomplete.text = formatted_address
                pass

    def on_touch_up(self, touch):
        if touch.grab_current == self:
            touch.ungrab(self)
            self._touch_count -= 1
            if self._touch_count == 0:
                self.update_marker_position()
                screen = self.manager.get_screen("client_location")
                screen.hide_modal_view()
                return True
        return super().on_touch_up(touch)


class Item(OneLineAvatarListItem):
    source = StringProperty()
    manager = ObjectProperty()

    def set_screen(self):
        print('dismiss dialog')
        screen = self.manager.get_screen("client_location")
        screen.hide_dialog()


class ItemConfirm(OneLineAvatarIconListItem):
    manager = ObjectProperty()

    def set_screen(self):
        print('next screen')
        screen = self.manager.get_screen("client_location")



class ClientLocation(MDScreen):
    API_KEY = "7060ef7890c44bb48d75f2d12c66a466"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.dialog = None
        self.longitude = None
        self.latitude = None
        self.geocoder = OpenCageGeocode(self.API_KEY)
        self.custom_modal_view = None

    def on_pre_enter(self):
        Clock.schedule_once(self.open_modal, 1)

    def open_modal(self, _):
        self.custom_modal_view = CustomModalView()
        self.custom_modal_view.open()
        self.show_modal_view()

    def search_location(self, instance, text):
        if text:
            url = f"https://api.opencagedata.com/geocode/v1/json?q={text}&key={self.API_KEY}"
            response = requests.get(url)
            if response.status_code == 200:
                data = response.json()
                results = data.get("results", [])
                if results:
                    if self.custom_modal_view:
                        self.custom_modal_view.ids.search_results.clear_widgets()
                        for result in results:
                            formatted_address = result.get("formatted")
                            if formatted_address:
                                item = OneLineIconListItem(IconLeftWidget(
                                    icon="map-marker"
                                ), text=formatted_address)
                                item.bind(on_release=self.on_location_selected)
                                self.custom_modal_view.ids.search_results.add_widget(item)
                else:
                    print("No results found.")
            else:
                print("Failed to fetch results.")
        else:
            print("Please enter a location to search.")

    def on_location_selected(self, instance):
        self.root.ids.autocomplete.text = instance.text

    def on_location(self, **kwargs):
        self.latitude = kwargs['lat']
        self.longitude = kwargs['lon']
        print(f"Latitude: {self.latitude}, Longitude: {self.longitude}")
        self.update_map_to_current_location()

    def fetch_location_details(self, instance):
        self.start_gps()

    def start_gps(self, *args):
        gps.start()

    def stop_gps(self):
        gps.stop()

    def update_map_to_current_location(self):
        if self.latitude is not None and self.longitude is not None:
            map_view = self.root.ids.map_view
            map_view.center_on(self.latitude, self.longitude)
            map_view.static_marker.lat = self.latitude
            map_view.static_marker.lon = self.longitude
            map_view.update_marker_position()

    def on_text_field_focus(self, instance, value):
        if value:
            self.show_modal_view()
        else:
            pass

    def show_modal_view(self):
        if not self.custom_modal_view:
            self.custom_modal_view = CustomModalView(size=(Window.width, Window.height - dp(150)))
        anim = Animation(opacity=1, duration=0.3)
        anim.start(self.custom_modal_view)
        self.custom_modal_view.open()

    def hide_modal_view(self):
        if self.custom_modal_view:
            anim = Animation(opacity=0, duration=0.3)
            anim.bind(on_complete=lambda *x: self.custom_modal_view.dismiss())
            anim.start(self.custom_modal_view)

    def show_confirmation_dialog(self):
        if not self.dialog:
            self.dialog = MDDialog(
                title="Someone else taking this appointment?",
                type="confirmation",
                items=[
                    Item(text="Myself", source="images/profile.jpg", manager=self.manager),
                    ItemConfirm(text="Choose another contact", manager=self.manager),

                ],
            )
        self.dialog.open()

    def hide_dialog(self):
        if self.dialog:
            self.dialog.dismiss()

    def back_button(self):
        self.hide_modal_view()
        self.manager.push_replacement('client_services')

