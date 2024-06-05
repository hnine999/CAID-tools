import re
import textx
import sys
from textx.metamodel import metamodel_from_file
from inspect import getfullargspec
import logging
import os

class Capability:
    def __init__(self, patterns: list[str]):
        self.patterns = patterns
        self.regexes = []
        for pattern in self.patterns:
            self.regexes.append(re.compile(pattern.replace('*', '.*')))

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.patterns == other.patterns
        return False

    def verify(self, *args):
        if len(args) != len(self.patterns):
            raise Exception("Can't verify capability, {} arguments given for {} patterns".format(
                len(args), len(self.patterns)))

        for i in range(0, len(args)):
            if self.regexes[i].fullmatch(args[i]) is None:
                return False
        return True

class CapLinkRead(Capability):
    def __init__(self, from_tool_id, from_rg, from_res, to_tool_id, to_rg, to_res):
        super().__init__([from_tool_id, from_rg, from_res, to_tool_id, to_rg, to_res])

class CapLinkAdd(Capability):
    def __init__(self, from_tool_id, from_rg, from_res, to_tool_id, to_rg, to_res):
        super().__init__([from_tool_id, from_rg, from_res, to_tool_id, to_rg, to_res])

class CapLinkRemove(Capability):
    def __init__(self, from_tool_id, from_rg, from_res, to_tool_id, to_rg, to_res):
        super().__init__([from_tool_id, from_rg, from_res, to_tool_id, to_rg, to_res])

class CapLinkMarkDirty(Capability):
    def __init__(self, from_tool_id, from_rg, from_res, to_tool_id, to_rg, to_res):
        super().__init__([from_tool_id, from_rg, from_res, to_tool_id, to_rg, to_res])

class CapLinkMarkClean(Capability):
    def __init__(self, from_tool_id, from_rg, from_res, to_tool_id, to_rg, to_res):
        super().__init__([from_tool_id, from_rg, from_res, to_tool_id, to_rg, to_res])

class CapResGroupRead(Capability):
    def __init__(self, tool_id_pattern, rg_pattern):
        super().__init__([tool_id_pattern, rg_pattern])

class CapResGroupAdd(Capability):
    def __init__(self, tool_id_pattern, rg_pattern):
        super().__init__([tool_id_pattern, rg_pattern])

class CapResGroupRemove(Capability):
    def __init__(self, tool_id_pattern, rg_pattern):
        super().__init__([tool_id_pattern, rg_pattern])

class CapResGroupChange(Capability):
    def __init__(self, tool_id_pattern, rg_pattern):
        super().__init__([tool_id_pattern, rg_pattern])

class CapResGroupWatch(Capability):
    def __init__(self, tool_id_pattern, rg_pattern):
        super().__init__([tool_id_pattern, rg_pattern])

class CapResourceRead(Capability):
    def __init__(self, tool_id_pattern, rg_pattern, res_pattern):
        super().__init__([tool_id_pattern, rg_pattern, res_pattern])

class CapResourceAdd(Capability):
    def __init__(self, tool_id_pattern, rg_pattern, res_pattern):
        super().__init__([tool_id_pattern, rg_pattern, res_pattern])

class CapResourceRemove(Capability):
    def __init__(self, tool_id_pattern, rg_pattern, res_pattern):
        super().__init__([tool_id_pattern, rg_pattern, res_pattern])

class CapResourceChange(Capability):
    def __init__(self, tool_id_pattern, rg_pattern, res_pattern):
        super().__init__([tool_id_pattern, rg_pattern, res_pattern])

class CapDepiWatch(Capability):
    def __init__(self):
        super().__init__([])

class CapBranchCreate(Capability):
    def __init__(self):
        super().__init__([])

class CapBranchSwitch(Capability):
    def __init__(self):
        super().__init__([])

class CapBranchList(Capability):
    def __init__(self):
        super().__init__([])

class CapBranchTag(Capability):
    def __init__(self):
        super().__init__([])

class Authorization:
    def __init__(self, rules=None, capabilities=None):
        self.caps = {}
        for rule in rules:
            for cap in rule:
                cap_name = cap.__class__.__name__
                if cap_name not in self.caps:
                    self.caps[cap_name] = [cap]
                else:
                    self.caps[cap_name].append(cap)

        for cap in capabilities:
            cap_name = cap.__class__.__name__
            if cap_name not in self.caps:
                self.caps[cap_name] = [cap]
            else:
                self.caps[cap_name].append(cap)

    def is_authorized(self, cls, *args):
        if cls.__name__ not in self.caps:
            return False

        for cap in self.caps[cls.__name__]:
            if cap.verify(*args):
                return True

        return False

    def has_capability(self, cls):
        return cls.__name__ in self.caps

    @staticmethod
    def find_capability(cap_str, patterns, line_number=0, config_source=""):
        cap_re = re.compile(cap_str.replace("*", ".*"))
        curr_module = sys.modules[Authorization.__module__]
        md = curr_module.__dict__
        caps = []
        for c_key in md:
            if isinstance(md[c_key], type) and md[c_key].__module__ == curr_module.__name__:
                cls = md[c_key]
                if cap_re.fullmatch(cls.__name__):
                    constructor = getattr(cls, "__new__")
                    instance = constructor(cls)
                    arg_spec = getfullargspec(instance.__init__)
                    if len(arg_spec.args) != len(patterns) + 1:
                        if line_number > 0:
                            logging.warning(("Skipping constructor in {} for {} matched by pattern {} on line {}," +
                                        "constructor takes {} patterns, but {} were supplied").format(
                                            config_source, cls.__name__, cap_str,
                                            line_number,
                                            len(arg_spec.args) - 1, len(patterns)))
                        else:
                            logging.warning("Skipping constructor in {} for {} matched by pattern {}" +
                                            "constructor takes {} patterns, but {} were supplied".format(
                                                config_source, cls.__name__, cap_str,
                                                len(arg_spec.args) - 1, len(patterns)))
                        continue
                    instance.__init__(*patterns)
                    caps.append(instance)
        return caps

    @staticmethod
    def create_from_user_config(user_auth_config, server_rules, user_name):
        if server_rules is None:
            server_rules = {}
        caps = []
        rules = []
        for auth_item in user_auth_config:
            if auth_item.startswith("Cap"):
                paren_start = auth_item.index('(')
                patterns = []
                if paren_start > 0:
                    paren_end = auth_item.index(')')
                    patterns = auth_item[paren_start+1:paren_end].split(",")
                new_caps = Authorization.find_capability(auth_item, patterns, 0,
                                                     "User "+user_name+" config")
                caps = caps + new_caps
            elif auth_item in server_rules:
                rules.append(server_rules[auth_item])
            else:
                logging.warning("Unknown server rule {} in config for user {}".format(
                    auth_item, user_name
                ))
        return Authorization(rules, caps)

auth_path = os.path.dirname(__file__)
auth_meta = metamodel_from_file(auth_path+"/auth.textx")

class AuthorizationConfigParser:
    def __init__(self):
        pass
    @staticmethod
    def parse_config_file(filename):
        try:
            config = auth_meta.model_from_file(filename)
            rules = {}
            for rule in config.rules:
                rule_name = rule.rule_name
                caps = []
                for cap in rule.rule_capabilities:
                    if isinstance(cap.cap.param, str):
                        cap_name = cap.cap.param
                    else:
                        cap_name = "".join(cap.cap.param)
                    patterns = []
                    if cap.parameter_list is not None:
                        for param in cap.parameter_list.params:
                            if isinstance(param.param, str):
                                patterns.append(param.param)
                            else:
                                patterns.append("".join(param.param))

                    caps = caps + Authorization.find_capability(cap_name, patterns,
                                    config._tx_parser.pos_to_linecol(cap.cap._tx_position)[0],
                                    filename)
                rules[rule_name] = caps

            return rules

        except textx.exceptions.TextXSyntaxError as exc:
            raise exc

#AuthorizationConfigParser.parse_config_file("depi_auth.txt")