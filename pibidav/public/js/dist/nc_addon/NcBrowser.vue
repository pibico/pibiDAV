<template>
  <div class="file-browser">
    <div class="nc-browser-list">
      <span class="flex align-center" 
        <v-row>
         <label for="nc_create_folder">NC Create Folder</label>
         <input type="checkbox" id="nc_create_folder" value="nc_create_folder" v-model="ncCreateFolder">
        </v-row>
         <label for="secret">Sharing Password</label>
         <input id="secret" v-model="secret"></input>
      
         <select v-model="shareType" class="form-select" aria-label="share Type">
           <option disabled value="">Select Share Type</option>
           <option>4-Upload Only</option>
           <option>17-Read Only</option>
           <option>31-Upload and Edit</option>
         </select>
      
      </span>
      <TreeNode
        class="tree with-skeleton"
        :node="node"
        :selected_node="selected_node"
        @node-click="n => toggle_node(n)"
        @load-more="n => load_more(n)"
      />
    </div>
  </div>
</template>
<script>
import TreeNode from "./TreeNode.vue";

export default {
  name: "NcBrowser",  
  components: {
    TreeNode
  },
  data() {
    return {
      secret: '',
      ncCreateFolder: false,
      shareType: '',
      node: {
        label: __("/"),
        value: "/",
        children: [],
        children_start: 0,
        children_loading: false,
        is_leaf: false,
        fetching: false,
        fetched: false,
        open: false
      },
      selected_node: {},
      page_length: 500
    };
  },
  mounted() {
    this.toggle_node(this.node);
  },
  methods: {
    toggle_node(node) {
      if (!node.is_leaf && !node.fetched) {
        node.fetching = true;
        node.children_start = 0;
        node.children_loading = false;
        this.get_files_in_folder(node.value, 0).then(
          ({ files, has_more }) => {
            node.open = true;
            node.children = files;
            node.fetched = true;
            node.fetching = false;
            node.children_start += this.page_length;
            node.has_more_children = has_more;
            this.select_node(node);
          }
        );
      } else {
        node.open = !node.open;
        this.select_node(node);
      }
    },
    load_more(node) {
      if (node.has_more_children) {
        let start = node.children_start;
        node.children_loading = true;
        this.get_files_in_folder(node.value, start).then(
          ({ files, has_more }) => {
            node.children = node.children.concat(files);
            node.children_start += this.page_length;
            node.has_more_children = has_more;
            node.children_loading = false;
          }
        );
      }
    },
    select_node(node) {
      //if (node.is_leaf) {
        this.selected_node = node;
      //}
    },
    get_files_in_folder(folder, start) {
      return frappe
      .call("pibidav.pibidav.custom.get_nc_files_in_folder", {
        folder,
        start,
        page_length: this.page_length
      })
      .then(r => {
        let { files = [], has_more = false } = r.message || {};
        files = files.map(file => this.make_file_node(file));
        return { files, has_more };
      });
    },
    make_file_node(file) {
      let filename = file.file_name || file.name;
      let label = frappe.utils.file_name_ellipsis(filename, 40);
      return {
        label: label,
        filename: filename,
        file_url: file.file_url,
        value: file.name,
        is_leaf: !file.is_folder,
        fetched: !file.is_folder, // fetched if node is leaf
        children: [],
        children_loading: false,
        children_start: 0,
        open: false,
        fetching: false
      };
    },
    select_folder() {
      let selected_file = this.selected_node;
      return this.upload_to_folder({
        is_folder: !selected_file.is_leaf,
	file_name: selected_file.filename,
        fileid: selected_file.file_url,
        path: selected_file.value
      });
    },
    upload_to_folder(file) {
      return file;
    }
  }
};
</script>

<style>
  .nc-browser-list {
    height: 300px;
    overflow: hidden;
    margin-top: 10px;
  }
  .tree {
    overflow: auto;
    height: 100%;
    padding-left: 0;
    padding-right: 0;
    padding-bottom: 4rem;
  }
</style>
