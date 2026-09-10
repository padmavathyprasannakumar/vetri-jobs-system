// =====================================================
// SUPER ADMIN API
// Vetri Jobs Platform Management
// =====================================================


import api from "./axios";






// =====================================================
// ADMIN DASHBOARD
// GET /api/admin/dashboard/
// =====================================================


export const getAdminDashboard = async()=>{


    try{


        return await api.get(

            "/admin/dashboard/"

        );


    }


    catch(error){


        console.error(

            "ADMIN DASHBOARD ERROR:",

            error.response?.data
            ||
            error.message

        );


        throw error;


    }


};









// =====================================================
// USER MANAGEMENT
// =====================================================


// GET ALL USERS

export const getAdminUsers = async()=>{


    try{


        return await api.get(

            "/admin/users/"

        );


    }


    catch(error){


        console.error(

            "GET USERS ERROR:",

            error.response?.data
            ||
            error.message

        );


        throw error;


    }


};








// UPDATE USER ROLE

export const updateUserRole = async(id,data)=>{


    return await api.patch(

        `/admin/users/${id}/role/`,

        data

    );


};








// UPDATE USER STATUS

export const updateUserStatus = async(id,data)=>{


    return await api.patch(

        `/admin/users/${id}/status/`,

        data

    );


};








// DELETE USER

export const deleteAdminUser = async(id)=>{


    return await api.delete(

        `/admin/users/${id}/`

    );


};









// =====================================================
// ROLE MANAGEMENT
// =====================================================


// GET ROLES

export const getAdminRoles = async()=>{


    return await api.get(

        "/admin/roles/"

    );


};








// CREATE ROLE

export const createRole = async(data)=>{


    return await api.post(

        "/admin/roles/create/",

        data

    );


};








// UPDATE ROLE

export const updateRole = async(id,data)=>{


    return await api.put(

        `/admin/roles/${id}/`,

        data

    );


};








// DELETE ROLE

export const deleteRole = async(id)=>{


    return await api.delete(

        `/admin/roles/${id}/`

    );


};









// =====================================================
// PERMISSION MANAGEMENT
// =====================================================


// GET PERMISSIONS

export const getPermissions = async()=>{


    return await api.get(

        "/admin/permissions/"

    );


};








// CREATE PERMISSION

export const createPermission = async(data)=>{


    return await api.post(

        "/admin/permissions/create/",

        data

    );


};








// UPDATE PERMISSION

export const updatePermission = async(id,data)=>{


    return await api.put(

        `/admin/permissions/${id}/`,

        data

    );


};








// DELETE PERMISSION

export const deletePermission = async(id)=>{


    return await api.delete(

        `/admin/permissions/${id}/`

    );


};









// =====================================================
// ANALYTICS
// =====================================================


// PLATFORM ANALYTICS

export const getAdminAnalytics = async()=>{


    return await api.get(

        "/admin/analytics/"

    );


};








// REPORT EXPORT

export const exportAdminReport = async(type)=>{


    return await api.get(

        `/admin/reports/export/?type=${type}`,

        {

            responseType:"blob"

        }

    );


};









// =====================================================
// SYSTEM SETTINGS
// =====================================================


export const getSystemSettings = async()=>{


    return await api.get(

        "/admin/settings/"

    );


};








export const updateSystemSettings = async(data)=>{


    return await api.put(

        "/admin/settings/",

        data

    );


};









// =====================================================
// CMS MANAGEMENT
// =====================================================


// HOME

export const updateHomeCMS = async(data)=>{


    return await api.put(

        "/home/",

        data

    );


};








// NAVBAR

export const updateNavbarCMS = async(data)=>{


    return await api.put(

        "/navbar/",

        data

    );


};








// FOOTER

export const updateFooterCMS = async(data)=>{


    return await api.put(

        "/footer/",

        data

    );


};









// =====================================================
// STUDENT MANAGEMENT
// =====================================================


export const getStudents = async()=>{


    return await api.get(

        "/placement/students/"

    );


};








export const verifyStudent = async(id,data)=>{


    return await api.patch(

        `/placement/students/${id}/verify/`,

        data

    );


};









// =====================================================
// COMPANY MANAGEMENT
// =====================================================


export const getCompanies = async()=>{


    return await api.get(

        "/placement/companies/"

    );


};








export const verifyCompany = async(id,data)=>{


    return await api.patch(

        `/placement/companies/${id}/verify/`,

        data

    );


};









// =====================================================
// CHATBOT MANAGEMENT
// =====================================================


export const getChatbotSettings = async()=>{


    return await api.get(

        "/chatbot/"

    );


};








export const updateChatbotSettings = async(data)=>{


    return await api.put(

        "/chatbot/",

        data

    );


};









// =====================================================
// WHATSAPP MANAGEMENT
// =====================================================


export const getWhatsAppSettings = async()=>{


    return await api.get(

        "/whatsapp/settings/"

    );


};








export const updateWhatsAppSettings = async(data)=>{


    return await api.put(

        "/whatsapp/settings/",

        data

    );


};









// =====================================================
// NOTIFICATION MANAGEMENT
// =====================================================


export const sendNotification = async(data)=>{


    return await api.post(

        "/notifications/send/",

        data

    );


};








export const getAllNotifications = async()=>{


    return await api.get(

        "/notifications/"

    );


};









// =====================================================
// AUDIT LOGS
// =====================================================


export const getAuditLogs = async()=>{


    return await api.get(

        "/admin/audit-logs/"

    );


};








// =====================================================
// ADMIN STATISTICS FORMATTER
// =====================================================


export const formatAdminStats=(data)=>{


    return {


        students:

            data.total_students
            ||
            0,


        companies:

            data.total_companies
            ||
            0,


        jobs:

            data.total_jobs
            ||
            0,


        applications:

            data.total_applications
            ||
            0,


        placements:

            data.total_placements
            ||
            0


    };


};









export default {


    getAdminDashboard,


    getAdminUsers,

    updateUserRole,

    updateUserStatus,

    deleteAdminUser,


    getAdminRoles,

    createRole,

    updateRole,

    deleteRole,


    getPermissions,

    createPermission,

    updatePermission,

    deletePermission,


    getAdminAnalytics,

    exportAdminReport,


    getSystemSettings,

    updateSystemSettings,


    updateHomeCMS,

    updateNavbarCMS,

    updateFooterCMS,


    getStudents,

    verifyStudent,


    getCompanies,

    verifyCompany,


    getChatbotSettings,

    updateChatbotSettings,


    getWhatsAppSettings,

    updateWhatsAppSettings,


    sendNotification,

    getAllNotifications,


    getAuditLogs,


    formatAdminStats


};