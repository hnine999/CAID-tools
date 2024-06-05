class DepiDB:
    HEAD="~~HEAD~~"

    def __init__(self):
        pass

    def load_version(self, project, version):
        raise NotImplementedError("load_version method is not implemented")
        
    def load_version_by_tag(self, project, tag):
        raise NotImplementedError("load_version_by_tag method is not implemented")
        
    def get_versions(self, name):
        raise NotImplementedError("get_versions method is not implemented")
        
    def get_tags(self, name):
        raise NotImplementedError("get_tags method is not implemented")
        
    def save_version(self, version, new_version_number):
        raise NotImplementedError("save_version method is not implemented")

    def tag_version(self, version, tag):
        raise NotImplementedError("tag_version method is not implemented")

    def untag_version(self, version, tag):
        raise NotImplementedError("untag_version method is not implemented")

#    def get_links_by_app(self, version, target_app):
#        raise NotImplementedError("get_links_by_app method is not implemented")
#
#    def get_links_by_endpoint(self, version, group, endpoint):
#        raise NotImplementedError("get_links_by_app method is not implemented")
#
#    def get_group(self, version, name, app_id):
#        raise NotImplementedError("get_group method is not implemented")
