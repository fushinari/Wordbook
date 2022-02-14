# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2016-2021 Mufeed Ali <fushinari@protonmail.com>
# SPDX-License-Identifier: GPL-3.0-or-later

import os

from gettext import gettext as _
from gi.repository import Gio, Gtk, Handy

from wordbook import utils
from wordbook.settings import Settings

PATH = os.path.dirname(__file__)


@Gtk.Template(resource_path=f"{utils.RES_PATH}/ui/settings_window.ui")
class SettingsWindow(Handy.PreferencesWindow):
    """Allows the user to customize Wordbook to some extent."""

    __gtype_name__ = "SettingsWindow"

    _double_click_switch = Gtk.Template.Child("double_click_switch")
    _live_search_switch = Gtk.Template.Child("live_search_switch")
    _pronunciations_accent_row = Gtk.Template.Child("pronunciations_accent_row")

    _dark_ui_switch = Gtk.Template.Child("dark_ui_switch")
    _dark_font_switch = Gtk.Template.Child("dark_font_switch")

    def __init__(self, parent, **kwargs):
        """Initialize the Settings window."""
        super().__init__(**kwargs)

        self.parent = parent

        # Pronunciations accent choices.
        liststore = Gio.ListStore.new(Handy.ValueObject)
        liststore.insert(0, Handy.ValueObject.new(_("American English")))
        liststore.insert(1, Handy.ValueObject.new(_("British English")))

        self._pronunciations_accent_row.bind_name_model(
            liststore, Handy.ValueObject.dup_string
        )

        self.load_settings()

        self._double_click_switch.connect(
            "notify::active", self._double_click_switch_activate
        )
        self._live_search_switch.connect(
            "notify::active", self._on_live_search_activate
        )
        self._dark_ui_switch.connect("notify::active", self._on_dark_ui_switch_activate)
        self._dark_font_switch.connect(
            "notify::active", self._on_dark_font_switch_activate
        )
        self._pronunciations_accent_row.connect(
            "notify::selected-index", self._on_pronunciations_accent_activate
        )

    def load_settings(self):
        """Load settings from the Settings instance."""
        self._double_click_switch.set_active(Settings.get().double_click)
        self._live_search_switch.set_active(Settings.get().live_search)
        self._pronunciations_accent_row.set_selected_index(
            Settings.get().pronunciations_accent_value
        )

        self._dark_ui_switch.set_active(Settings.get().gtk_dark_ui)
        self._dark_font_switch.set_active(Settings.get().gtk_dark_font)

    @staticmethod
    def _double_click_switch_activate(switch, _gparam):
        """Change 'double click to search' state."""
        Settings.get().double_click = switch.get_active()

    def _on_live_search_activate(self, switch, _gparam):
        """Change live search state."""
        self.parent.completer.set_popup_completion(not switch.get_active())
        Settings.get().live_search = switch.get_active()

    @staticmethod
    def _on_pronunciations_accent_activate(row, _gparam):
        """Change pronunciations' accent."""
        Settings.get().pronunciations_accent_value = row.get_selected_index()

    @staticmethod
    def _on_dark_ui_switch_activate(switch, _gparam):
        """Change UI theme."""
        Settings.get().gtk_dark_ui = switch.get_active()
        Handy.StyleManager.get_default().set_color_scheme(
            Handy.ColorScheme.FORCE_DARK
            if switch.get_active()
            else Handy.ColorScheme.PREFER_LIGHT
        )

    def _on_dark_font_switch_activate(self, switch, _gparam):
        """Change definitions' font colors."""
        Settings.get().gtk_dark_font = switch.get_active()
        self.__refresh_view()

    def __refresh_view(self):
        """Refresh definition view."""
        if self.parent.searched_term is not None:
            self.parent.on_search_clicked(
                pass_check=True, text=self.parent.searched_term
            )
