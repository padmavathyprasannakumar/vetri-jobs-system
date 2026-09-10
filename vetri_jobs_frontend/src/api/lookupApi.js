import api from "./axios";


// =====================================================
// PUBLIC LOOKUP LISTS
// Departments / Courses / Job Categories - fully managed
// by the Super Admin via Django Admin. Any form that needs
// these dropdowns should call this instead of hardcoding
// options, so admin-configured changes show up everywhere
// automatically.
// =====================================================


export const getLookupLists = async(departmentId)=>{

    try{

        return await api.get(

            "/lookups/",

            departmentId
                ? { params: { department: departmentId } }
                : {}

        );

    }

    catch(error){

        console.error(

            "LOOKUP LISTS ERROR:",

            error.response?.data || error.message

        );

        throw error;

    }

};


export default {
    getLookupLists,
};
