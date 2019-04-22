import sys
import json

# import subprocess
# def install(package):
#     subprocess.call([sys.executable, "-m", "pip", "install", package])
# install("python-dateutil")
# install("colorama")
# install("shlex")
# install("uuid")

import datetime
from dateutil import parser as dateparser
import argparse
import shlex
from colorama import Fore, Back, Style
#Fore: BLACK, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE, RESET.
#Back: BLACK, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE, RESET.
#Style: DIM, NORMAL, BRIGHT, RESET_ALL
import uuid
import readline
import editor
#from pick import pick
#from difflib import SequenceMatcher

import warnings
with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    from fuzzywuzzy import fuzz

if sys.version_info >= (3, 0):
    sys_input = input
else:
    sys_input = raw_input

class AliasedSubParsersAction(argparse._SubParsersAction):

    class _AliasedPseudoAction(argparse.Action):
        def __init__(self, name, aliases, help):
            dest = name
            if aliases:
                dest += ' (%s)' % ','.join(aliases)
            sup = super(AliasedSubParsersAction._AliasedPseudoAction, self)
            sup.__init__(option_strings=[], dest=dest, help=help)

    def add_parser(self, name, **kwargs):
        if 'aliases' in kwargs:
            aliases = kwargs['aliases']
            del kwargs['aliases']
        else:
            aliases = []

        parser = super(AliasedSubParsersAction, self).add_parser(name, **kwargs)

        # Make the aliases work.
        for alias in aliases:
            self._name_parser_map[alias] = parser
        # Make the help text reflect them, first removing old help entry.
        if 'help' in kwargs:
            help = kwargs.pop('help')
            self._choices_actions.pop()
            pseudo_action = self._AliasedPseudoAction(name, aliases, help)
            self._choices_actions.append(pseudo_action)

        return parser

class TimestampDiffPrinter:
    def __init__(self):
        self.last_printed_timestamp = ""

    def print_timestamp(self, new_timestamp):
        diff_timestamp = ""
        found_diff = False
        for c1, c2 in zip(new_timestamp, self.last_printed_timestamp):
            if c1 != c2:
                found_diff = True
            if not found_diff:#c1 == c2:
                diff_timestamp += Style.DIM +  Fore.WHITE + c1 + Style.RESET_ALL
            else:
                diff_timestamp += c1
        self.last_printed_timestamp = new_timestamp
        if len(diff_timestamp) != len(new_timestamp):
            diff_timestamp += new_timestamp[len(diff_timestamp):]
        return diff_timestamp

    def reset(self):
        self.last_printed_timestamp = ""

class Interface:
    NOTES_FILE = "notes.txt"
    HISTORY_FILE = 'history.txt'

    def __init__(self):
        self.timestamp_diff_printer = TimestampDiffPrinter()

        self.entries = []
        self.selected_entries = []
        try:
            with open(self.NOTES_FILE) as f:
                for line in f:
                    if len(line) > 1:
                        self.entries.append(json.loads(line))
            #print("{}".format(entries))
        except FileNotFoundError:
            pass

        try:
            readline.read_history_file(Interface.HISTORY_FILE)
        except FileNotFoundError:
            pass

        with open(self.HISTORY_FILE, "a") as f:
            if len(sys.argv) > 1:  # ignore script running without arguments
                f.write("{}\n".format(" ".join(sys.argv)))

        self.parser = argparse.ArgumentParser()
        self.parser.register('action', 'parsers', AliasedSubParsersAction)
        subparsers = self.parser.add_subparsers(dest='command', metavar="COMMAND")
        parser_exit = subparsers.add_parser('exit', help="ends the interactive session.")  # , prefix_chars = '\0')
        parser_add = subparsers.add_parser('add', help="adds a new note to the file.")  # , prefix_chars = '\0')
        parser_add.add_argument("-s", "--start", dest="start", action='store', type=str)
        parser_add.add_argument("-e", "--end", dest="end", action='store', type=str)
        parser_add.add_argument('content', type=str, nargs='?')

        parser_find = subparsers.add_parser('find',
                                            help="find all notes with a given string.")  # , prefix_chars = '\0')
        parser_find.add_argument('find_str', type=str)
        parser_find.add_argument("-s", "--strictness", dest="strictness", action='store', type=float, default=0.50)
        self.parser.add_argument('-b', "--before", dest="before", action='store', type=str, default="")
        self.parser.add_argument('-a', "--after", dest="after", action='store', type=str, default="")

        parser_list = subparsers.add_parser('list', help="list entries.", aliases=('ls',))  # , prefix_chars = '\0')
        parser_delete = subparsers.add_parser('del', help="delete entries.")
        parser_delete.add_argument(dest="index_selection", action='store', type=str)
        parser_interact = subparsers.add_parser('interact', help="interactive session.")
        parser_edit = subparsers.add_parser('edit', help="edit note.")
        parser_edit.add_argument(dest="index", action='store', type=int, default=-1, nargs='?')

        readline.parse_and_bind("tab: complete")

    def run(self):
        if len(sys.argv) == 1:
            args = argparse.Namespace()
            args.command = "interact"
        else:
            args = self.parser.parse_args()
        self.process_input(args)
        if args.command == None:
            self.interact()

    def interact(self):
        while True:
            raw_in = sys_input('>')
            #print("raw: {}, type: {}".format(raw_in, type(raw_in)))
            input_str = shlex.split(raw_in)  # this splits the string the same way as it happens for argv
            #print("{}".format(input_str))
            with open(self.HISTORY_FILE, "a") as f:
                f.write("{}\n".format(" ".join(input_str)))
            args = self.parser.parse_args(input_str)  # .split())
            self.process_input(args)

    def save(self):
        self.entries.sort(key=lambda entry: entry["creationtime"])
        with open(self.NOTES_FILE, "w") as outfile:
            for entry in self.entries:
                if entry is not None:
                    json.dump(entry, outfile)#, sort_keys=True, indent=1, default=default)
                    outfile.write("\n")
                    
    def shutdown(self):
        self.save() 
        raise SystemExit

    def similarity(self, search_key, pattern):
        #return SequenceMatcher(a=search_key, b=pattern).partial_ratio()
        #return fuzz.token_set_ratio(search_key, pattern)
        #return fuzz.ratio(search_key, pattern)
        return fuzz.partial_ratio(search_key, pattern)

    def add_note(self, args):
        #print(args)
        content = args.content
        #with open(self.NOTES_FILE, 'a') as outfile:
        if content == None:
           content = editor.edit()
        entry = dict()
        entry["content"] = content
        entry["creationtime"] = str(datetime.datetime.now())#[:-7]
        if args.start is not None:
            entry["starttime"] = str(dateparser.parse(args.start))#[:-7]
        if args.end is not None:
            entry["endttime"] = str(dateparser.parse(args.end))#[:-7]
        entry["uuid"] = str(uuid.uuid4())
        #json.dump(entry, outfile)#, sort_keys=True, indent=1, default=default)
        #outfile.write("\n")
        self.entries.append(entry)
        self.save()

    def get_entry_string(self, index, entry, highlight_content_word="", highlight_whole_entry=False):
        if highlight_whole_entry:
            string = Fore.RED
        else:
            string = ""
        if highlight_content_word != "":
            matched_str_part = Fore.RED + highlight_content_word + Style.RESET_ALL
            content_str = matched_str_part.join(entry["content"].split(highlight_content_word))
        else:
            content_str = entry["content"]
        string += "{:<5} {:20} {:<50} ".format(index,
                                             self.timestamp_diff_printer.print_timestamp(entry["creationtime"][:19]), content_str.strip(),
                                                {k: v for k, v in entry.items() if k not in ["creationtime", "content"]})
        if highlight_whole_entry:
            string += Style.RESET_ALL
        return string


    def find(self, args):
        find_str = args.find_str
        strictness = args.strictness
        before = args.before
        after = args.after
        #print("{}".format(args))
        found_entries = []
        for entry in self.entries:
            pattern = str(entry["content"])
            sim = self.similarity(find_str, pattern)
            if sim > strictness*100:
                if before == "" or dateparser.parse(entry["creationtime"]) < dateparser.parse(before):
                    if after == "" or dateparser.parse(entry["creationtime"]) > dateparser.parse(after):
                        found_entries.append((sim, entry))
        found_entries.sort(key=lambda tup: tup[0])
        self.selected_entries = [tup[1] for tup in found_entries]
        self.timestamp_diff_printer.reset()
        for i, (sim, entry) in enumerate(found_entries):
            print("{:3d}% {}".format(sim,self.get_entry_string(i, entry, find_str)))

    def list(self, args):
        before = args.before
        after = args.after
        self.timestamp_diff_printer.reset()
        for i, entry in enumerate(self.entries):
            if before == "" or dateparser.parse(entry["creationtime"]) < dateparser.parse(before):
                if after == "" or dateparser.parse(entry["creationtime"]) > dateparser.parse(after):
                    print(self.get_entry_string(i, entry))
        self.selected_entries = self.entries

    def edit(self, args):
        index = args.index

        entry = self.selected_entries[index]
        new_content = editor.edit(contents=entry["content"])
        entry["content"] = new_content

    def delete(self, args):
        if len(self.selected_entries) == 0:
            print("nothing is selected!")
        else:
            index_selection = args.index_selection
            deleted_entries = []

            try:
                index = int(index_selection)
                deleted_entries.append(self.selected_entries[index])
            except ValueError:
                range = index_selection.split(":")
                start, end = int(range[0]), int(range[1])
                deleted_entries = self.selected_entries[start:end]
            new_entries = []
            print("deleted entries:")
            for i, entry in enumerate(self.entries):
                if entry in deleted_entries:
                    print(self.get_entry_string(i, entry, highlight_whole_entry=True))
                else:
                    new_entries.append(entry)
            self.entries = new_entries
            #self.entries = [x for x in self.entries if x not in self.selected_entries[start:end]]

        #self.entries = [entry for entry in self.entries if entry is not None]
        self.selected_entries = []

    # def delete(self, args):
    #     options = [self.get_entry_string(entry) for entry in self.selected_entries]
    #     selection = pick(options, "select entries to delete:", multi_select=True)
    #     uuids_to_delete = []
    #     for text, index in selection:
    #         uuids_to_delete.append(self.selected_entries[index]["uuid"])
    #     self.entries = [x for x in self.entries if not x["uuid"] in uuids_to_delete]
    #     print("deleted uuids: {}".format(uuids_to_delete))



    def process_input(self, args):
        print(args)
        if args.command == "add":
            self.add_note(args)
        elif args.command == "find":
            self.find(args)
            #find(args.find_str, strictness=args.strictness, before=args.before, after=args.after)
        elif args.command == "list" or args.command == "ls":
            self.list(args)
            #list(before=args.before, after=args.after)
        elif args.command == "del":
            self.delete(args)
        elif args.command == "interact":
            self.interact()
        elif args.command == "exit":
            self.shutdown()
        elif args.command == "edit":
            self.edit(args)

if __name__ == "__main__":
    interface = Interface()
    interface.run()
