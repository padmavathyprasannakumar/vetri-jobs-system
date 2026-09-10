// =====================================================
// SITE CONTENT API
// Vetri Jobs CMS Module
//
// Used by:
// - Public Website
// - Super Admin CMS Management
//
// =====================================================


import api from "./axios";





// =====================================================
// HOME PAGE CONTENT
// GET /api/home/
// =====================================================


export const getHomeContent = async()=>{


    try{


        return await api.get(

            "/home/"

        );


    }


    catch(error){


        console.error(

            "GET HOME CONTENT ERROR:",

            error.response?.data
            ||
            error.message

        );


        throw error;


    }


};








// =====================================================
// UPDATE HOME CONTENT
// ADMIN ONLY
//
// PUT /api/home/
// =====================================================


export const updateHomeContent = async(data)=>{


    try{


        return await api.put(

            "/home/",

            data

        );


    }


    catch(error){


        console.error(

            "UPDATE HOME CONTENT ERROR:",

            error.response?.data
            ||
            error.message

        );


        throw error;


    }


};








// =====================================================
// NAVBAR CONTENT
// GET /api/navbar/
// =====================================================


export const getNavbarContent = async()=>{


    try{


        return await api.get(

            "/navbar/"

        );


    }


    catch(error){


        console.error(

            "GET NAVBAR ERROR:",

            error.response?.data
            ||
            error.message

        );


        throw error;


    }


};








// =====================================================
// UPDATE NAVBAR CONTENT
// ADMIN ONLY
//
// PUT /api/navbar/
// =====================================================


export const updateNavbarContent = async(data)=>{


    try{


        return await api.put(

            "/navbar/",

            data

        );


    }


    catch(error){


        console.error(

            "UPDATE NAVBAR ERROR:",

            error.response?.data
            ||
            error.message

        );


        throw error;


    }


};








// =====================================================
// FOOTER CONTENT
// GET /api/footer/
// =====================================================


export const getFooterContent = async()=>{


    try{


        return await api.get(

            "/footer/"

        );


    }


    catch(error){


        console.error(

            "GET FOOTER ERROR:",

            error.response?.data
            ||
            error.message

        );


        throw error;


    }


};








// =====================================================
// UPDATE FOOTER CONTENT
// ADMIN ONLY
//
// PUT /api/footer/
// =====================================================


export const updateFooterContent = async(data)=>{


    try{


        return await api.put(

            "/footer/",

            data

        );


    }


    catch(error){


        console.error(

            "UPDATE FOOTER ERROR:",

            error.response?.data
            ||
            error.message

        );


        throw error;


    }


};








// =====================================================
// GET ALL CMS CONTENT
// =====================================================
//
// Example:
// About
// Services
// Contact
// FAQ
//
// GET /api/site-content/
// =====================================================


export const getSiteContent = async()=>{


    try{


        return await api.get(

            "/site-content/"

        );


    }


    catch(error){


        console.error(

            "GET SITE CONTENT ERROR:",

            error.response?.data
            ||
            error.message

        );


        throw error;


    }


};








// =====================================================
// GET SINGLE CONTENT
//
// GET /api/site-content/:id/
// =====================================================


export const getSiteContentById = async(id)=>{


    try{


        return await api.get(

            `/site-content/${id}/`

        );


    }


    catch(error){


        console.error(

            "GET CONTENT DETAIL ERROR:",

            error.response?.data
            ||
            error.message

        );


        throw error;


    }


};








// =====================================================
// UPDATE CMS CONTENT
// ADMIN ONLY
//
// PUT /api/site-content/:id/
// =====================================================


export const updateSiteContent = async(id,data)=>{


    try{


        return await api.put(

            `/site-content/${id}/`,

            data

        );


    }


    catch(error){


        console.error(

            "UPDATE SITE CONTENT ERROR:",

            error.response?.data
            ||
            error.message

        );


        throw error;


    }


};








// =====================================================
// CREATE CMS CONTENT
// ADMIN ONLY
//
// POST /api/site-content/
// =====================================================


export const createSiteContent = async(data)=>{


    try{


        return await api.post(

            "/site-content/",

            data

        );


    }


    catch(error){


        console.error(

            "CREATE SITE CONTENT ERROR:",

            error.response?.data
            ||
            error.message

        );


        throw error;


    }


};








// =====================================================
// DELETE CMS CONTENT
// ADMIN ONLY
//
// DELETE /api/site-content/:id/
// =====================================================


export const deleteSiteContent = async(id)=>{


    try{


        return await api.delete(

            `/site-content/${id}/`

        );


    }


    catch(error){


        console.error(

            "DELETE SITE CONTENT ERROR:",

            error.response?.data
            ||
            error.message

        );


        throw error;


    }


};








// =====================================================
// CONTENT FORMATTER
// =====================================================


export const formatHomeContent=(data)=>{


    return {


        title:

            data.title
            ||
            "Vetri Jobs",



        subtitle:

            data.subtitle
            ||
            "Find your dream career",



        banner:

            data.banner
            ||
            null,


        description:

            data.description
            ||
            ""


    };


};








export default {


    getHomeContent,

    updateHomeContent,


    getNavbarContent,

    updateNavbarContent,


    getFooterContent,

    updateFooterContent,


    getSiteContent,

    getSiteContentById,

    createSiteContent,

    updateSiteContent,

    deleteSiteContent,


    formatHomeContent


};