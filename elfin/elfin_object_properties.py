import bpy
import mathutils

from . import livebuild_helper as LH

class Linkage(bpy.types.PropertyGroup):
    terminus = bpy.props.StringProperty()
    source_chain_id = bpy.props.StringProperty()
    target_mod = bpy.props.PointerProperty(type=bpy.types.Object)
    target_chain_id = bpy.props.StringProperty()

    def __repr__(self):
        return 'Linkage => (Src CID={}, Tgt={}, Tgt CID={})'.format(
            self.source_chain_id, self.target_mod, self.target_chain_id)

    def sever(self):
        if self.target_mod:
            target_nl = self.target_mod.elfin.n_linkage \
                if self.terminus == 'c' else \
                self.target_mod.elfin.c_linkage
            print('Severing: ', repr(self))

            # Remove back reference
            target_nl[self.target_chain_id].target_mod = None
            target_nl.remove(target_nl.find(self.target_chain_id))

        # Remove forward reference
        self.target_mod = None

class ObjectPointerWrapper(bpy.types.PropertyGroup):
    obj = bpy.props.PointerProperty(type=bpy.types.Object)

class ElfinObjectProperties(bpy.types.PropertyGroup):
    """Represents an elfin object (module/joint/bridge)."""
    obj_type = bpy.props.IntProperty(default=LH.ElfinObjType.NONE.value)
    module_name = bpy.props.StringProperty()
    module_type = bpy.props.StringProperty()
    obj_ptr = bpy.props.PointerProperty(type=bpy.types.Object)

    c_linkage = bpy.props.CollectionProperty(type=Linkage)
    n_linkage = bpy.props.CollectionProperty(type=Linkage)
    pg_neighbours = bpy.props.CollectionProperty(type=ObjectPointerWrapper)

    def is_module(self):
        return self.obj_type == LH.ElfinObjType.MODULE.value

    def is_joint(self):
        return self.obj_type == LH.ElfinObjType.PG_JOINT.value

    def is_bridge(self):
        return self.obj_type == LH.ElfinObjType.PG_BRIDGE.value

    def destroy(self):
        """Delete an object using default delete operator while preserving
        selection before deletion.
        """

        if self.is_module():
            self.cleanup_module()
        elif self.is_joint():
            self.cleanup_joint()
        elif self.is_bridge():
            self.cleanup_bridge()
        else:
            return # No obj_ptr to delete

        LH.delete_object(self.obj_ptr)

    def cleanup_bridge(self):
        """Remove references of self object and also pointer to joints"""
        for opw in self.pg_neighbours:
            if opw.obj:
                rem_idx = -1
                jnb = opw.obj.elfin.pg_neighbours
                for i in range(len(jnb)):
                    if jnb[i].obj == self.obj_ptr:
                        rem_idx = i
                        break
                if rem_idx != -1:
                    jnb.remove(rem_idx)

    def cleanup_joint(self):
        """Delete connected bridges"""

        while len(self.pg_neighbours) > 0:
            self.pg_neighbours[0].obj.elfin.destroy()


    def cleanup_module(self):
        self.sever_links()

        # Destroy mirrors
        for m in self.mirrors:
            if m != self.obj_ptr:
                m.elfin.mirrors = []
                m.elfin.destroy()

        print('Module {} cleaned up.'.format(self.obj_ptr))


    def create_bridge(self, joint_a, joint_b):
        # Cache locations
        jb_loc = mathutils.Vector(joint_b.location)

        # Move ja and jb to default locations
        joint_b.location = joint_a.location + mathutils.Vector([0, 5, 0])

        bridge = self.obj_ptr
        bridge.parent = joint_b

        bridge.constraints.new(type='COPY_LOCATION').target = joint_a
        bridge.constraints.new(type='COPY_ROTATION').target = joint_a

        stretch_cons = bridge.constraints.new(type='STRETCH_TO')
        stretch_cons.target = joint_b
        stretch_cons.bulge = 0.0

        bridge.elfin.pg_neighbours.add().obj = joint_a
        bridge.elfin.pg_neighbours.add().obj = joint_b
        joint_a.elfin.pg_neighbours.add().obj = bridge
        joint_b.elfin.pg_neighbours.add().obj = bridge

        # Restore joint_b location 
        # 
        # [!] Must call update so that constraints don't bug out. This works
        # normally in Blender console if you copy paste the code of this
        # function but will break in script if update() is not called.
        bpy.context.scene.update()
        joint_b.location = jb_loc

    def new_c_link(self, source_chain_id, target_mod, target_chain_id):
        link = self.c_linkage.add()
        link.name = link.source_chain_id = source_chain_id
        link.terminus = 'c'
        link.target_mod = target_mod
        link.target_chain_id = target_chain_id

    def new_n_link(self, source_chain_id, target_mod, target_chain_id):
        link = self.n_linkage.add()
        link.name = link.source_chain_id = source_chain_id
        link.terminus = 'n'
        link.target_mod = target_mod
        link.target_chain_id = target_chain_id

    def show_links(self):
        print('Links of {}'.format(self.obj_ptr.name))
        print('C links:')
        for cl in self.c_linkage: print(repr(cl))
        print('N links:')
        for nl in self.n_linkage: print(repr(nl))

    def sever_links(self):
        for cl in self.c_linkage: cl.sever()
        for nl in self.n_linkage: nl.sever()

    @property
    def mirrors(self):
        return self.get('_mirrors', [])

    @mirrors.setter
    def mirrors(self, value):
        self['_mirrors'] = value
