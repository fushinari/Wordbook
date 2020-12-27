# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2016-2020 Mufeed Ali <fushinari@protonmail.com>
# SPDX-License-Identifier: GPL-3.0-or-later

import os
import random
import threading
from html import escape

from gi.repository import Gdk, Gio, GLib, Gtk, Handy

from wordbook import base, utils
from wordbook.settings_window import SettingsWindow
from wordbook.settings import Settings


@Gtk.Template(resource_path=f"{utils.RES_PATH}/ui/window.ui")
class WordbookGtkWindow(Handy.ApplicationWindow):
    __gtype_name__ = "WordbookGtkWindow"

    _header_bar = Gtk.Template.Child("header_bar")
    _search_entry = Gtk.Template.Child("search_entry")
    _search_button = Gtk.Template.Child("search_button")
    _speak_button = Gtk.Template.Child("speak_button")
    _clear_button = Gtk.Template.Child("clear_button")
    _menu_button = Gtk.Template.Child("wordbook_menu_button")
    _stack = Gtk.Template.Child("main_stack")
    _loading_label = Gtk.Template.Child("loading_label")
    _loading_progress = Gtk.Template.Child("loading_progress")
    _def_view = Gtk.Template.Child("def_view")
    _pronunciation_view = Gtk.Template.Child("pronunciation_view")
    _term_view = Gtk.Template.Child("term_view")

    _complete_list = []
    _completion_request_count = 0
    _loading_max = None
    _loading_progress_fraction = 0.0
    _loading_pulse_state = False
    _pasted = False
    _searched_term = None
    _wn_downloader = base.WordnetDownloader()
    _wn_future = None

    def __init__(self, **kwargs):
        """Initialize the window."""
        super().__init__(**kwargs)

        if Gio.Application.get_default().development_mode is True:
            self.get_style_context().add_class('devel')

        builder = Gtk.Builder.new_from_resource(f"{utils.RES_PATH}/ui/menu.xml")
        menu = builder.get_object("wordbook-menu")
        self.set_icon_name(utils.APP_ID)

        popover = Gtk.Popover.new_from_model(self._menu_button, menu)
        self._menu_button.set_popover(popover)

        self.connect("notify::is-maximized", self._on_window_state_changed)
        self.connect("key-press-event", self._on_key_press_event)
        self._clear_button.connect("clicked", self._on_clear_clicked)
        self._def_view.connect("button-press-event", self._on_def_event)
        self._def_view.connect("activate-link", self._on_link_activated)
        self._search_button.connect("clicked", self._on_search_clicked)
        self._search_entry.connect("changed", self._on_entry_changed)
        self._search_entry.connect("drag-data-received", self._on_drag_received)
        self._search_entry.connect("paste-clipboard", self._on_paste_done)
        self._speak_button.connect("clicked", self._on_speak_clicked)

        # Loading and setup.
        self._header_bar.set_sensitive(False)
        if not self._wn_downloader.check_status():
            self._loading_label.set_text("Downloading WordNet...")
            threading.Thread(
                target=self._wn_downloader.download, args=[self.__progress_update]
            ).start()
        else:
            self._wn_future = base.get_wn_file()
            self._header_bar.set_sensitive(True)
            self.__page_switch("welcome_page")

        # Completions. This is kept separate because it uses its own weird logic.
        # This and related code might need refactoring later on.
        self._completer = Gtk.EntryCompletion()
        self._completer_liststore = Gtk.ListStore(str)
        self._completer.set_text_column(0)
        self._completer.set_model(self._completer_liststore)
        self._completer.set_popup_completion(not Settings.get().live_search)
        self._completer.get_popup_completion()
        self._search_entry.set_completion(self._completer)
        self._completer.connect("action-activated", self._on_entry_completed)

    def on_about(self, _action, _param):
        """Show the about window."""
        about_dialog = Gtk.AboutDialog(transient_for=self, modal=True)
        about_dialog.set_logo_icon_name(utils.APP_ID)
        about_dialog.set_program_name("Wordbook")
        about_dialog.set_version(utils.VERSION)
        about_dialog.set_comments("Wordbook is a simple dictionary application.")
        about_dialog.set_authors(
            [
                "Mufeed Ali",
            ]
        )
        about_dialog.set_license_type(Gtk.License.GPL_3_0)
        about_dialog.set_website("https://www.github.com/fushinari/wordbook")
        about_dialog.set_copyright("Copyright © 2016-2020 Mufeed Ali")
        about_dialog.connect("response", lambda dialog, response: dialog.destroy())
        about_dialog.present()

    def on_paste_search(self, _action, _param):
        """Search text in clipboard."""
        text = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).wait_for_text()
        text = base.cleaner(text)
        if text is not None and not text.strip() == "" and not text.isspace():
            GLib.idle_add(self._search_entry.set_text, text)
            GLib.idle_add(self._on_search_clicked)
            GLib.idle_add(self._search_entry.grab_focus)

    def on_preferences(self, _action, _param):
        """Show settings window."""
        window = SettingsWindow(transient_for=self)
        window.connect("destroy", self._on_preferences_destroy)
        window.load_settings()
        window.present()

    def on_random_word(self, _action, _param):
        """Search a random word from the wordlist."""
        random_word = random.choice(self._wn_future.result()["list"])
        random_word = random_word.replace("_", " ")
        GLib.idle_add(self._search_entry.set_text, random_word)
        GLib.idle_add(self._on_search_clicked, pause=False, text=random_word)
        GLib.idle_add(self._search_entry.grab_focus)

    def on_search_selected(self, _action, _param):
        """Search selected text from inside or outside the window."""
        text = Gtk.Clipboard.get(Gdk.SELECTION_PRIMARY).wait_for_text()
        if text is not None and not text.strip() == "" and not text.isspace():
            text = text.replace("         ", "").replace("\n", "")
            GLib.idle_add(self._search_entry.set_text, text)
            GLib.idle_add(self._on_search_clicked, pause=False, text=text)
            GLib.idle_add(self._search_entry.grab_focus)

    def on_shortcuts(self, _action, _param):
        """Launch the Keyboard Shortcuts window."""
        builder = Gtk.Builder.new_from_resource(
            f"{utils.RES_PATH}/ui/shortcuts_window.ui"
        )
        shortcuts_window = builder.get_object("shortcuts")
        shortcuts_window.set_transient_for(self)
        shortcuts_window.show()

    def _on_clear_clicked(self, _button):
        """Clear all text in the window."""
        GLib.idle_add(self._def_view.set_text, "")
        GLib.idle_add(self._pronunciation_view.set_text, "")
        GLib.idle_add(self._term_view.set_text, "")
        GLib.idle_add(self._search_entry.set_text, "")
        GLib.idle_add(self._speak_button.set_visible, False)
        self.__page_switch("welcome_page")

    def _on_def_event(self, _eventbox, event):
        """Search on double click."""
        if (
            Settings.get().double_click
            and event.type == Gdk.EventType.DOUBLE_BUTTON_PRESS
        ):
            text = Gtk.Clipboard.get(Gdk.SELECTION_PRIMARY).wait_for_text()
            if text is not None and not text.strip() == "" and not text.isspace():
                text = text.split(" ")[0]
                GLib.idle_add(self._search_entry.set_text, text)
                GLib.idle_add(self._on_search_clicked, pause=False, text=text)
                GLib.idle_add(self._search_entry.grab_focus)

    def _on_drag_received(self, _widget, _drag_context, _x, _y, _data, _info, _time):
        """Search on receiving drag and drop event."""
        self._search_entry.set_text("")
        GLib.idle_add(self.__entry_cleaner)
        GLib.idle_add(self._search_entry.set_position, -1)
        GLib.idle_add(self._on_search_clicked)

    def _on_entry_changed(self, _entry):
        """Detect changes to text and do live search if enabled."""
        self._completion_request_count += 1
        if self._completion_request_count == 1:
            threading.Thread(
                target=self.__update_completions,
                args=[self._search_entry.get_text()],
                daemon=True,
            ).start()
        if self._pasted is True:
            self.__entry_cleaner()
            self._pasted = False
        if Settings.get().live_search:
            GLib.idle_add(self._on_search_clicked)

    def _on_entry_completed(self, _entry_completion, index):
        """Enter text into the entry using completions."""
        self._search_entry.set_text(self._complete_list[index])
        self._search_entry.set_position(-1)
        GLib.idle_add(self._on_search_clicked)

    def _on_key_press_event(self, _widget, event):
        """Focus onto the search entry when needed (quick search)."""
        modifiers = event.get_state() & Gtk.accelerator_get_default_mod_mask()

        shift_mask = Gdk.ModifierType.SHIFT_MASK
        key_unicode = Gdk.keyval_to_unicode(event.keyval)
        if GLib.unichar_isgraph(chr(key_unicode)) and modifiers in (shift_mask, 0):
            self._search_entry.grab_focus_without_selecting()

    def _on_link_activated(self, _widget, data):
        """Search for terms that are marked as hyperlinks."""
        if data.startswith("search:"):
            GLib.idle_add(self._search_entry.set_text, data[7:])
            self._on_search_clicked(pause=False, text=data[7:])

    def _on_paste_done(self, _widget):
        """Cleanup pasted data."""
        self._pasted = True

    def _on_preferences_destroy(self, _window):
        """Refresh view when Preferences window is closed."""
        self._completer.set_popup_completion(not Settings.get().live_search)
        if self._searched_term is not None:
            self._on_search_clicked(
                pass_check=True, pause=False, text=self._searched_term
            )

    def _on_search_clicked(self, _button=None, pass_check=False, pause=True, text=None):
        """Pass data to search function and set TextView data."""
        if not text:
            text = self._search_entry.get_text().strip()

        except_list = ("fortune -a", "cowfortune")
        if pass_check or not text == self._searched_term or text in except_list:
            if pause:
                GLib.idle_add(self._def_view.set_text, "")
                GLib.idle_add(self._pronunciation_view.set_text, "")
                GLib.idle_add(self._term_view.set_text, "")
                GLib.idle_add(self._speak_button.set_visible, False)

            self._searched_term = text
            if not text.strip() == "":
                out = self.__search(text)

                if out is None:
                    return

                if out["definition"] is not None:
                    self.__page_switch("content_page")
                    out_text = base.clean_pango(f'{out["definition"]}')
                    GLib.idle_add(self._def_view.set_markup, out_text)
                else:
                    self.__page_switch("fail_page")
                    return

                GLib.idle_add(
                    self._term_view.set_markup,
                    f'<span size="large" weight="bold">{out["term"].strip()}</span>',
                )
                GLib.idle_add(
                    self._pronunciation_view.set_markup,
                    f'<i>{out["pronunciation"].strip()}</i>',
                )

                if text not in except_list and out["term"] != "Lookup failed.":
                    GLib.idle_add(self._speak_button.set_visible, True)

                return

            self.__page_switch("welcome_page")
            return

    def _on_speak_clicked(self, _button):
        """Say the search entry out loud with espeak speech synthesis."""
        speed = "120"  # To change eSpeak-ng audio speed.
        text = self._searched_term
        base.read_term(text, speed)

    def _on_window_state_changed(self, _window, _state):
        """Detect changes to the window state and adapt."""
        if Settings.get().gtk_max_hide and not os.environ.get("GTK_CSD") == "0":
            if self.props.is_maximized:
                GLib.idle_add(self._header_bar.set_show_close_button, False)
            else:
                GLib.idle_add(self._header_bar.set_show_close_button, True)

    def __progress_update(self, chunk, count=0, max=0, status=None):
        """
        Update Wordnet download/build progress in the UI.
        """
        elements = [
            "ILI",
            "Synsets",
            "Definitions",
            "Synset Relations",
            "Words",
            "Word Forms",
            "Senses",
            "Sense Relations",
            "Examples",
        ]
        if status == "Initializing" or status == "Requesting":
            GLib.idle_add(self._loading_label.set_label, status)
        elif status == "Receiving" and max:
            self._loading_max = float(max)
        elif status is None and chunk:
            self._loading_progress_fraction = self._loading_progress_fraction + (
                chunk / self._loading_max
            )
            GLib.idle_add(
                self._loading_progress.set_fraction, self._loading_progress_fraction
            )
        elif status == "Complete\n":
            self._loading_progress_fraction = 0.0
            GLib.idle_add(
                self._loading_progress.set_fraction, self._loading_progress_fraction
            )
            GLib.idle_add(self._loading_label.set_label, "Building database...")
        elif status is None and max:
            self._loading_max = float(max)
        elif status in elements and chunk == 0:
            GLib.idle_add(self._loading_label.set_label, f"Building {status}...")
        elif status == "":
            GLib.idle_add(self._loading_label.set_label, "Ready.")
            self._wn_future = base.get_wn_file()
            GLib.idle_add(self._header_bar.set_sensitive, True)
            self.__page_switch("welcome_page")

    def __entry_cleaner(self):
        term = self._search_entry.get_text()
        self._search_entry.set_text(base.cleaner(term))

    def __new_error(self, primary_text, seconday_text):
        """Show an error dialog."""
        dialog = Gtk.MessageDialog(
            self, 0, Gtk.MessageType.ERROR, Gtk.ButtonsType.OK, primary_text
        )
        dialog.format_secondary_text(seconday_text)
        dialog.run()
        dialog.destroy()

    def __page_switch(self, page):
        if self._stack.get_visible_child_name == page:
            return True
        GLib.idle_add(self._stack.set_visible_child_name, page)
        return False

    def __search(self, search_text):
        """Clean input text, give errors and pass data to reactor."""
        text = base.cleaner(search_text)
        if not text == "" and not text.isspace():
            self.__page_switch("content_page")
            return base.reactor(
                text,
                Settings.get().gtk_dark_font,
                self._wn_future.result()["instance"],
                Settings.get().cdef,
            )
        self.__page_switch("welcome_page")
        if not Settings.get().live_search:
            self.__new_error(
                "Invalid Input",
                "Wordbook thinks that your input was actually just a bunch of useless "
                "characters. And so, an 'Invalid Characters' error.",
            )
        self._searched_term = None
        return None

    def __update_completions(self, text):
        while self._completion_request_count > 0:
            while len(self._complete_list) > 0:
                GLib.idle_add(self._completer.delete_action, 0)
                self._complete_list.pop(0)

            for item in self._wn_future.result()["list"]:
                item = item.replace("_", " ")
                if item.lower().startswith(text.lower()):
                    self._complete_list.append(item.replace("_", " "))
                if len(self._complete_list) == 10:
                    break

            for item in os.listdir(utils.CDEF_DIR):
                if len(self._complete_list) >= 10:
                    break
                item = escape(item).replace("_", " ")
                if item in self._complete_list:
                    self._complete_list.remove(item)
                if item.lower().startswith(text.lower()):
                    self._complete_list.append(f"<i>{item}</i>")

            self._complete_list = sorted(self._complete_list)
            for item in self._complete_list:
                GLib.idle_add(
                    self._completer.insert_action_markup,
                    self._complete_list.index(item),
                    item,
                )

            self._completion_request_count -= 1
