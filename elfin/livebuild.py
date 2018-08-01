import bpy

from . import addon_paths
from .livebuild_helper import *


# Global (Const) Variables -----------------------

# Color Change Placeholder
#   Insert a placeholder as the first option for Place/Extrude operator enums
#   so that user can change the color before choosing a module. This makes
#   changing display color fast because once a module is selected via the
#   enum, changing the displace color causes constant re-linking and that
#   causes lag.
color_change_placeholder = '-Change Color-'
color_change_placeholder_enum_tuple = \
    (color_change_placeholder, color_change_placeholder, '')


# Operators --------------------------------------

class ListMirrors(bpy.types.Operator):
    bl_idname = 'elfin.list_mirrors'
    bl_label = 'List mirror links of one selected module'
    bl_options = {'REGISTER'}

    def execute(self, context):
        mirrors = get_selected().elfin.mirrors
        mirror_strs = []
        for i in range(len(mirrors)):
            mirror_strs.append('[{}] {}'.format(i, mirrors[i].name))
        print('Mirror String: ', mirror_strs)
        MessagePrompt.message_lines=mirror_strs
        bpy.ops.elfin.message_prompt('INVOKE_DEFAULT',
            title='List Mirror Result',
            icon='INFO')
        return {'FINISHED'}

    @classmethod
    def poll(cls, context):
        return get_selection_len() == 1 and  \
            get_selected().elfin.is_module

class UnlinkMirrors(bpy.types.Operator):
    bl_idname = 'elfin.unlink_mirrors'
    bl_label = 'Unlink mirrors from all selected modules.'
    bl_options = {'REGISTER', 'UNDO'}

    def unlink_mirrors(self, mirrors, recursive):
        if recursive:
            for o in get_selected(-1):
                for m in o.elfin.mirrors:
                    if m != o: m.elfin.mirrors = []
                o.elfin.mirrors = []
        else:
            for o in get_selected(-1):
                o.elfin.mirrors = []

        MessagePrompt.message_lines=['Operation successful']
        bpy.ops.elfin.message_prompt('INVOKE_DEFAULT',
            title='Unlink Mirrors',
            icon='INFO')

    def execute(self, context):
        mirrors = get_selected(-1) 
        YesNoPrmopt.callback_true = \
            YesNoPrmopt.Callback(self.unlink_mirrors, [mirrors, True])
        YesNoPrmopt.callback_false = \
            YesNoPrmopt.Callback(self.unlink_mirrors, [mirrors, False])
        bpy.ops.elfin.yes_no_prompt('INVOKE_DEFAULT',
            option=True,
            title='Unlink recursively?',
            message='Yes')

        return {'FINISHED'}

    @classmethod
    def poll(self, context):
        return get_selection_len() > 0

class LinkByMirror(bpy.types.Operator):
    bl_idname = 'elfin.link_by_mirror'
    bl_label = 'Link multiple modules of the same prototype by mirror.'
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def can_link(cls):
        """Only show operator if selected objects are of the same prototype
        """
        selection = get_selected(-1)
        if selection:
            mod_name = selection[0].elfin.module_name
            for o in selection:
                if not o.elfin.is_module or o.elfin.module_name != mod_name:
                    return False
            return True

    def link_by_mirror(self, mirrors):
        for m in mirrors:
            m.elfin.mirrors = mirrors
        MessagePrompt.message_lines=['Operation successful']
        bpy.ops.elfin.message_prompt('INVOKE_DEFAULT',
            title='Link by Mirror',
            icon='INFO')

    def execute(self, context):
        if not LinkByMirror.can_link():
            self.report(
                {'ERROR'}, 
                ('Selection is not homogenous i.e. some selected modules '
                    ' have a different prototype'))
            return {'CANCELLED'}

        mirrors = get_selected(-1)

        # Check for existing mirrors and warn user about it
        existing = False
        for m in mirrors:
            if m.elfin.mirrors:
                existing = True
                break

        if existing:
            YesNoPrmopt.callback_true = \
                YesNoPrmopt.Callback(self.link_by_mirror, [mirrors])
            bpy.ops.elfin.yes_no_prompt('INVOKE_DEFAULT',
                option=False,
                title='{} already has mirrors. Replace?'.format(m.name),
                message='Yes, replace.')
        else:
            self.link_by_mirror(mirrors)

        return {'FINISHED'}

    @classmethod
    def poll(cls, context):
        return cls.can_link()

class JoinNetworks(bpy.types.Operator):
    bl_idname = 'elfin.join_networks'
    bl_label = 'Join two compatible networks'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        raise NotImplementedError

class ExtrudeNTerm(bpy.types.Operator):
    bl_idname = 'elfin.extrude_nterm_internal'
    bl_label = 'Internal N Terminal extrusion operator'
    bl_options = {'REGISTER', 'INTERNAL'}

    target_name = bpy.props.StringProperty()
    nterm_ext_module_selector = bpy.props.StringProperty()
    color = bpy.props.FloatVectorProperty()

    def execute(self, context):
        ext_mod = None
        try:
            xdb = get_xdb()

            sel_mod = context.scene.objects[self.target_name]
            sel_mod_name = sel_mod.elfin.module_name
            sel_mod.select = False

            # Enum selector format: extrude_into:module_name:extrude_from.
            extrude_into, nterm_mod_name, extrude_from = \
                self.nterm_ext_module_selector.split('.')
            ext_mod = link_module(nterm_mod_name)
            print('Extruding module {} (chain {}) from {}\'s N-Term (chain {})'.format(
                self.nterm_ext_module_selector, 
                extrude_into, 
                sel_mod_name, 
                extrude_from))

            def touch_up_new_mod(sel_mod, new_mod, sel_mod_chain_id=extrude_from):
                give_module_new_color(new_mod, self.color)
                new_mod.hide = False # Unhide (default is hidden)
                sel_mod.elfin.new_n_link(sel_mod_chain_id, new_mod, extrude_into)
                new_mod.elfin.new_c_link(extrude_into, sel_mod, sel_mod_chain_id)
                new_mod.select = True

            sel_ext_type_pair = (sel_mod.elfin.module_type, ext_mod.elfin.module_type)
            if sel_ext_type_pair == ('single', 'single'):
                def extrude_single_single(sel_mod, new_mod):
                    rel = xdb['double_data'][nterm_mod_name][sel_mod_name]
                    drop_frame(new_mod, rel, fixed_mod=sel_mod)
                    touch_up_new_mod(sel_mod, new_mod)
                    return new_mod

                extrude_single_single(sel_mod, ext_mod)

                if sel_mod.elfin.mirrors:
                    create_module_mirrors(
                        sel_mod, 
                        [ext_mod], 
                        nterm_mod_name, 
                        extrude_single_single)
            elif sel_ext_type_pair == ('single', 'hub'):
                def extrude_single_hub(sel_mod, new_mod):
                    # First drop to hub component frame
                    chain_xdata = xdb \
                        ['hub_data'][nterm_mod_name]\
                        ['component_data'][extrude_into]
                    rel = chain_xdata['c_connections'][sel_mod_name]
                    drop_frame(new_mod, rel)

                    # Second drop to double B frame
                    rel = xdb \
                        ['double_data'][chain_xdata['single_name']][sel_mod_name]
                    drop_frame(new_mod, rel, fixed_mod=sel_mod)
                    touch_up_new_mod(sel_mod, new_mod)
                    return new_mod

                extrude_single_hub(sel_mod, ext_mod)

                if sel_mod.elfin.mirrors:
                    create_module_mirrors(
                        sel_mod,
                        [ext_mod],
                        nterm_mod_name,
                        extrude_single_hub
                        )
            elif sel_ext_type_pair == ('hub', 'single'):
                hub_xdata = xdb['hub_data'][sel_mod_name]
                comp_xdata = hub_xdata['component_data']
                def extrude_single_at_chain(sel_mod, new_mod, src_chain_id):
                    chain_xdata = comp_xdata[src_chain_id]
                    rel = chain_xdata['n_connections'][nterm_mod_name]
                    raise_frame(new_mod, rel, fixed_mod=sel_mod)
                    touch_up_new_mod(sel_mod, new_mod, src_chain_id)

                def extrude_hub_single(sel_mod, new_mod):
                    extrude_single_at_chain(sel_mod, new_mod, extrude_from)

                    if hub_xdata['symmetric']:
                        hub_n_free_chains = \
                            set(hub_xdata['component_data'].keys()) - \
                            set(sel_mod.elfin.n_linkage.keys())
                        mirrors = [new_mod]
                        
                        for src_chain_id in hub_n_free_chains:
                            mirror_mod = link_module(nterm_mod_name)
                            extrude_single_at_chain(sel_mod, mirror_mod, src_chain_id)
                            mirrors.append(mirror_mod)

                        for m in mirrors:
                            m.elfin.mirrors = mirrors

                        return None # Mirrers are taken care of here already
                    else:
                        return new_mod

                extrude_hub_single(sel_mod, ext_mod)

                if sel_mod.elfin.mirrors:
                    create_module_mirrors(
                        sel_mod,
                        [] if hub_xdata['symmetric'] else [ext_mod],
                        nterm_mod_name,
                        extrude_hub_single)
            elif sel_ext_type_pair == ('hub', 'hub'):
                self.report({'ERROR'}, 'Unimplemented')
                return {'CANCELLED'}
            else:
                raise ValueError('Invalid sel_ext_type_pair: {}'.format(sel_ext_type_pair))

            return {'FINISHED'}
        except Exception as e:
            if ext_mod:
                ext_mod.elfin.destroy()
            sel_mod.select = True # Restore selection
            raise e
        return {'FINISHED'}

class ExtrudeCTerm(bpy.types.Operator):
    bl_idname = 'elfin.extrude_cterm_internal'
    bl_label = 'Internal C Terminal extrusion operator'
    bl_options = {'REGISTER', 'INTERNAL'}

    target_name = bpy.props.StringProperty()
    cterm_ext_module_selector = bpy.props.StringProperty()
    color = bpy.props.FloatVectorProperty()

    def execute(self, context):
        ext_mod = None
        try:
            xdb = get_xdb()

            sel_mod = context.scene.objects[self.target_name]
            sel_mod_name = sel_mod.elfin.module_name
            sel_mod.select = False

            # Enum selector format: extrude_from:module_name:extrude_into.
            extrude_from, cterm_mod_name, extrude_into = \
                self.cterm_ext_module_selector.split('.')
            ext_mod = link_module(cterm_mod_name)
            print('Extruding module {} (chain {}) from {}\'s C-Term (chain {})'.format(
                self.cterm_ext_module_selector, extrude_into, sel_mod_name, extrude_from))

            def touch_up_new_mod(sel_mod, new_mod, sel_mod_chain_id=extrude_from):
                give_module_new_color(new_mod, self.color)
                new_mod.hide = False # Unhide (default is hidden)
                sel_mod.elfin.new_c_link(sel_mod_chain_id, new_mod, extrude_into)
                new_mod.elfin.new_n_link(extrude_into, sel_mod, sel_mod_chain_id)
                new_mod.select = True

            sel_ext_type_pair = (sel_mod.elfin.module_type, ext_mod.elfin.module_type)
            if sel_ext_type_pair == ('single', 'single'):
                def extrude_single_single(sel_mod, new_mod):
                    rel = xdb['double_data'][sel_mod_name][cterm_mod_name]
                    raise_frame(new_mod, rel, fixed_mod=sel_mod)
                    touch_up_new_mod(sel_mod, new_mod)
                    return new_mod

                extrude_single_single(sel_mod, ext_mod)

                if sel_mod.elfin.mirrors:
                    create_module_mirrors(
                        sel_mod, 
                        [ext_mod], 
                        cterm_mod_name, 
                        extrude_single_single)
            elif sel_ext_type_pair == ('single', 'hub'):
                def extrude_single_hub(sel_mod, new_mod):
                    chain_xdata = xdb\
                        ['hub_data'][cterm_mod_name] \
                        ['component_data'][extrude_into]
                    rel = chain_xdata['n_connections'][sel_mod_name]
                    drop_frame(new_mod, rel, fixed_mod=sel_mod)
                    touch_up_new_mod(sel_mod, new_mod)
                    return new_mod

                extrude_single_hub(sel_mod, ext_mod)

                if sel_mod.elfin.mirrors:
                    create_module_mirrors(
                        sel_mod,
                        [ext_mod],
                        cterm_mod_name,
                        extrude_single_hub
                        )
            elif sel_ext_type_pair == ('hub', 'single'):
                hub_xdata = xdb['hub_data'][sel_mod_name]
                comp_xdata = hub_xdata['component_data']
                def extrude_single_at_chain(sel_mod, new_mod, src_chain_id):
                    chain_xdata = comp_xdata[src_chain_id]

                    # First raise to double B frame
                    rel = xdb['double_data'] \
                        [chain_xdata['single_name']][cterm_mod_name]
                    raise_frame(new_mod, rel)

                    # Second raise to hub component frame
                    rel = chain_xdata['c_connections'][cterm_mod_name]
                    raise_frame(new_mod, rel, fixed_mod=sel_mod)
                    touch_up_new_mod(sel_mod, new_mod, src_chain_id)
                    
                def extrude_hub_single(sel_mod, new_mod):
                    extrude_single_at_chain(sel_mod, new_mod, extrude_from)

                    if hub_xdata['symmetric']:
                        hub_c_free_chains = \
                            set(hub_xdata['component_data'].keys()) - \
                            set(sel_mod.elfin.c_linkage.keys())
                        mirrors = [new_mod]

                        for src_chain_id in hub_c_free_chains:
                            mirror_mod = link_module(cterm_mod_name)
                            extrude_single_at_chain(mirror_mod, src_chain_id)
                            mirrors.append(mirror_mod)

                        for m in mirrors:
                            m.elfin.mirrors = mirrors

                        return None # Mirrers are taken care of here already
                    else:
                        return new_mod

                extrude_hub_single(sel_mod, ext_mod)

                if sel_mod.elfin.mirrors:
                    create_module_mirrors(
                        sel_mod,
                        [] if hub_xdata['symmetric'] else [ext_mod],
                        cterm_mod_name,
                        extrude_hub_single)
            elif sel_ext_type_pair == ('hub', 'hub'):
                self.report({'ERROR'}, 'Unimplemented')
                return {'CANCELLED'}
            else:
                raise ValueError('Invalid sel_ext_type_pair: {}'.format(sel_ext_type_pair))

            return {'FINISHED'}
        except Exception as e:
            if ext_mod:
                ext_mod.elfin.destroy()
            sel_mod.select = True # Restore selection
            raise e
        return {'FINISHED'}

class ModuleExtrudeNTerm(bpy.types.Operator):
    bl_idname = 'elfin.module_extrude_nterm'
    bl_label = 'Extrude N (add a module to the nterm)'
    bl_property = "nterm_ext_module_selector"
    bl_options = {'REGISTER', 'UNDO'}

    def modlib_filter_enum_cb(self, context):
        enum_tuples = [color_change_placeholder_enum_tuple]

        # Selection length is guranteed by poll()
        sel_mod = get_selected()
        sel_mod_name = sel_mod.elfin.module_name
        sel_mod_type = sel_mod.elfin.module_type

        xdb = get_xdb()
        if sel_mod_type == 'hub':
            hub_xdata = xdb['hub_data'][sel_mod_name]
            occupied_n_termini = sel_mod.elfin.n_linkage.keys()
            for chain_id, chain_xdata in hub_xdata['component_data'].items():
                if chain_id in occupied_n_termini:
                    continue
                for single_name in chain_xdata['n_connections']:
                    enum_tuples.append(
                        module_enum_tuple(
                            single_name, 
                            extrude_from=chain_id, 
                            extrude_into='A',
                            direction='N'))
                if hub_xdata['symmetric']:
                    # Only allow one chain to be extruded because other
                    # "mirrors" will be generated automatically
                    break
        elif sel_mod_type == 'single':
            if len(sel_mod.elfin.n_linkage) == 0:
                for single_a_name in xdb['single_data']:
                    if sel_mod_name in xdb['double_data'][single_a_name]:
                        enum_tuples.append(
                            module_enum_tuple(
                                single_a_name,
                                extrude_from='A',
                                extrude_into='A',
                                direction='N'))
                for hub_name in xdb['hub_data']:
                    if xdb['hub_data'][hub_name]['symmetric']:
                        # Logically one can never extrude a symmetric hub
                        # See README development notes
                        continue
                    for hub_comp_name in \
                        get_compatible_hub_components(hub_name, 'C', sel_mod_name):
                        enum_tuples.append(
                            module_enum_tuple(
                                hub_name, 
                                extrude_from='A',
                                extrude_into=hub_comp_name,
                                direction='N'))
        else:
            raise ValueError('Unknown module type: ', sel_mod_type)
        if len(enum_tuples) == 1:
            # Remove color change placeholder if nothing can be extruded
            enum_tuples = []
        return enum_tuples

    nterm_ext_module_selector = bpy.props.EnumProperty(items=modlib_filter_enum_cb)
    color = bpy.props.FloatVectorProperty(name="Display Color", 
                                        subtype='COLOR', 
                                        default=[0,0,0])

    def execute(self, context):
        if self.nterm_ext_module_selector != color_change_placeholder:
            filter_mirror_selection()
            # Cache the selector because due to UI oddities the self attribute
            # could change in the following loop.
            selector = self.nterm_ext_module_selector
            for s in get_selected(-1):
                bpy.ops.elfin.extrude_nterm_internal(
                    target_name=s.name, 
                    nterm_ext_module_selector=selector,
                    color=self.color
                )
        return {'FINISHED'}

    def invoke(self, context, event):
        self.color = ColorWheel().next_color()
        context.window_manager.invoke_search_popup(self)
        return {'FINISHED'}

    @classmethod
    def poll(cls, context):
        return suitable_for_extrusion(context)

class ModuleExtrudeCTerm(bpy.types.Operator):
    bl_idname = 'elfin.module_extrude_cterm'
    bl_label = 'Extrude C (add a module to the cterm)'
    bl_property = "cterm_ext_module_selector"
    bl_options = {'REGISTER', 'UNDO'}

    def modlib_filter_enum_cb(self, context):
        enum_tuples = [color_change_placeholder_enum_tuple]

        # Selection length is guranteed by poll()
        sel_mod = get_selected()
        sel_mod_name = sel_mod.elfin.module_name
        sel_mod_type = sel_mod.elfin.module_type

        xdb = get_xdb()
        if sel_mod_type == 'hub':
            hub_xdata = xdb['hub_data'][sel_mod_name]
            occupied_c_termini = sel_mod.elfin.c_linkage.keys()
            for chain_id, chain_xdata in hub_xdata['component_data'].items():
                if chain_id in occupied_c_termini:
                    continue
                for single_name in chain_xdata['c_connections']:
                    enum_tuples.append(
                        module_enum_tuple(
                            single_name, 
                            extrude_from=chain_id, 
                            extrude_into='A',
                            direction='C')) 
                if hub_xdata['symmetric']:
                    # Only allow one chain to be extruded because other
                    # "mirrors" will be generated automatically
                    break
        elif sel_mod_type == 'single':
            if len(sel_mod.elfin.c_linkage) == 0:
                sel_mod_xdata = xdb['double_data'][sel_mod_name]
                for single_b_name in sel_mod_xdata:
                    enum_tuples.append(
                        module_enum_tuple(
                            single_b_name,
                            extrude_from='A',
                            extrude_into='A',
                            direction='C'))
                for hub_name in xdb['hub_data']:
                    if xdb['hub_data'][hub_name]['symmetric']:
                        # Logically one can never extrude a symmetric hub
                        # See README development notes
                        continue
                    for hub_comp_name in \
                        get_compatible_hub_components(hub_name, 'N', sel_mod_name):
                        enum_tuples.append(
                            module_enum_tuple(
                                hub_name, 
                                extrude_from='A',
                                extrude_into=hub_comp_name,
                                direction='C'))
        else:
            raise ValueError('Unknown module type: ', sel_mod_type)

        if len(enum_tuples) == 1:
            # Remove color change placeholder if nothing can be extruded
            enum_tuples = []
        return enum_tuples

    cterm_ext_module_selector = bpy.props.EnumProperty(items=modlib_filter_enum_cb)
    color = bpy.props.FloatVectorProperty(name="Display Color", 
                                        subtype='COLOR', 
                                        default=[0,0,0],
                                        options={'LIBRARY_EDITABLE'})

    def execute(self, context):
        if self.cterm_ext_module_selector != color_change_placeholder:
            filter_mirror_selection()
            # See comment in ModuleExtrudeNTerm
            selector = self.cterm_ext_module_selector
            for s in get_selected(-1):
                bpy.ops.elfin.extrude_cterm_internal(
                    target_name=s.name, 
                    cterm_ext_module_selector=selector,
                    color=self.color
                )
        return {'FINISHED'}

    def invoke(self, context, event):
        self.color = ColorWheel().next_color()
        context.window_manager.invoke_search_popup(self)
        return {'FINISHED'}

    @classmethod
    def poll(cls, context):
        return suitable_for_extrusion(context)

class LoadXdb(bpy.types.Operator):
    bl_idname = 'elfin.load_xdb'
    bl_label = '(Re)load xdb'

    def execute(self, context):
        xdb = get_xdb()
        xdb.clear()
        xdb.update(load_xdb())
        return {'FINISHED'}

class LoadModuleLibrary(bpy.types.Operator):
    bl_idname = 'elfin.load_module_library'
    bl_label = '(Re)load module library'

    def execute(self, context):
        context.scene.elfin.library.clear()
        context.scene.elfin.library.extend(load_module_library())
        return {'FINISHED'}

class MessagePrompt(bpy.types.Operator):
    """Elfin Module Collision Message"""
    bl_idname = 'elfin.message_prompt'
    bl_label = 'Prompts a message with an OK button.'
    bl_options = {'REGISTER', 'INTERNAL'}

    title = bpy.props.StringProperty(default='Elfin Message')
    icon = bpy.props.StringProperty(default='ERROR')
    message_lines = []

    def execute(self, context):
        # Manually reset values
        self.message_lines = []
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_popup(self)
 
    def draw(self, context):
        self.layout.label(self.title, icon=self.icon)
        row = self.layout.column()
        for l in self.message_lines:
            row.label(l)

# Credits to
# https://blender.stackexchange.com/questions/73286/how-to-call-a-confirmation-dialog-box
class YesNoPrmopt(bpy.types.Operator):
    bl_idname = 'elfin.yes_no_prompt'
    bl_label = 'Confirm option'
    bl_options = {'REGISTER', 'INTERNAL'}
    
    title = bpy.props.StringProperty(default='Confirm?')
    icon = bpy.props.StringProperty(default='QUESTION')

    message = bpy.props.StringProperty(default='No')
    option = bpy.props.BoolProperty(default=True)

    class Callback:
        def __init__(self, func=None, args=[], kwargs=[]):
            self.func = func
            self.args = args
            self.kwargs = kwargs

    callback_true = Callback()
    callback_false = Callback()

    def execute(self, context):
        if self.option and self.callback_true.func:
            self.callback_true.func(
                *self.callback_true.args, 
                *self.callback_true.kwargs)
        elif self.callback_false.func:
            self.callback_false.func(
                *self.callback_false.args, 
                *self.callback_false.kwargs)

        # Manually reset values
        self.callback_true = self.Callback()
        self.callback_false = self.Callback()
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        row = self.layout
        row.label(self.title, icon=self.icon)
        row.prop(self, 'option', text=self.message)

class CheckCollisionAndDelete(bpy.types.Operator):
    bl_idname = 'elfin.check_collision_and_delete'
    bl_label = 'Check collision and delete if positive'

    # Allow keyword specification
    object_name = bpy.props.StringProperty(default='__unset__')

    def execute(self, context):
        found_overlap = False

        try:
            ob = bpy.data.objects[self.object_name]
            found_overlap |= delete_if_overlap(ob)
        except KeyError:
            # No valid object_name specified - use selection
            for ob in get_selected(-1):
                if ob.elfin.is_module:
                    found_overlap |= delete_if_overlap(ob)
                else:
                    print('No overlap: {}'.format(ob.name))

        if found_overlap:
            MessagePrompt.message_lines=['Collision was detected and modules were deleted.']
            bpy.ops.elfin.message_prompt('INVOKE_DEFAULT')
        return {'FINISHED'}

    def invoke(self, context, event):
        self.object_name = ''

class PlaceModule(bpy.types.Operator):
    bl_idname = 'elfin.place_module'
    bl_label = 'Place a module'
    bl_property = 'selected_module'
    bl_options = {'REGISTER', 'UNDO'}

    def modlib_enum_cb(self, context):
        res = [color_change_placeholder_enum_tuple]
        for mod_name in context.scene.elfin.library:
            if '-' not in mod_name: # This is a check for "not double module"
                res.append(module_enum_tuple(mod_name))
        return res

    selected_module = bpy.props.EnumProperty(items=modlib_enum_cb)
    color = bpy.props.FloatVectorProperty(name="Display Color", 
                                        subtype='COLOR', 
                                        default=[0,0,0])

    def execute(self, context):
        if self.selected_module == color_change_placeholder:
            return {'FINISHED'}

        print('Placing module {}'.format(self.selected_module))
        
        sel_mod_name = self.selected_module.split('.')[1]
        lmod = link_module(sel_mod_name)

        give_module_new_color(lmod, self.color)
        lmod.hide = False # By default the obj is hidden
        lmod.select = True

        return {'FINISHED'}

    def invoke(self, context, event):
        self.color = ColorWheel().next_color()
        context.window_manager.invoke_search_popup(self)

        return {'FINISHED'}

    @classmethod
    def poll(cls, context):
        return get_selection_len() == 0