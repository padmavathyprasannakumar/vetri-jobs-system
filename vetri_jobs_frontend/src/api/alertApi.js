// =====================================================
// ALERT / NOTIFICATION API
// =====================================================

import api from "./axios";



// =====================================================
// GET ALL NOTIFICATIONS
// GET /api/notifications/
// =====================================================

export const getNotifications = async()=>{

    try{


        const response = await api.get(

            "/notifications/"

        );


        return response;


    }


    catch(error){


        console.error(

            "GET NOTIFICATIONS ERROR:",

            error.response?.data
            ||
            error.message

        );


        throw error;


    }

};






// =====================================================
// GET USER NOTIFICATION COUNT
// GET /api/notifications/count/
// =====================================================

export const getNotificationCount = async()=>{


    try{


        const response = await api.get(

            "/notifications/count/"

        );


        return response;


    }


    catch(error){


        console.error(

            "NOTIFICATION COUNT ERROR:",

            error.response?.data
            ||
            error.message

        );


        throw error;


    }


};







// =====================================================
// GET SINGLE NOTIFICATION
// GET /api/notifications/:id/
// =====================================================

export const getNotificationById = async(id)=>{


    try{


        const response = await api.get(

            `/notifications/${id}/`

        );


        return response;


    }


    catch(error){


        console.error(

            "GET NOTIFICATION DETAIL ERROR:",

            error.response?.data
            ||
            error.message

        );


        throw error;


    }


};







// =====================================================
// MARK NOTIFICATION AS READ
// PATCH /api/notifications/:id/read/
// =====================================================

export const markNotificationRead = async(id)=>{


    try{


        const response = await api.patch(

            `/notifications/${id}/read/`

        );


        return response;


    }


    catch(error){


        console.error(

            "MARK NOTIFICATION READ ERROR:",

            error.response?.data
            ||
            error.message

        );


        throw error;


    }


};







// =====================================================
// MARK ALL NOTIFICATIONS READ
// PATCH /api/notifications/read-all/
// =====================================================

export const markAllNotificationsRead = async()=>{


    try{


        const response = await api.patch(

            "/notifications/read-all/"

        );


        return response;


    }


    catch(error){


        console.error(

            "MARK ALL NOTIFICATION ERROR:",

            error.response?.data
            ||
            error.message

        );


        throw error;


    }


};







// =====================================================
// DELETE NOTIFICATION
// DELETE /api/notifications/:id/
// =====================================================

export const deleteNotification = async(id)=>{


    try{


        const response = await api.delete(

            `/notifications/${id}/`

        );


        return response;


    }


    catch(error){


        console.error(

            "DELETE NOTIFICATION ERROR:",

            error.response?.data
            ||
            error.message

        );


        throw error;


    }


};







// =====================================================
// SEND NOTIFICATION (ADMIN / PLACEMENT)
// POST /api/notifications/send/
// =====================================================

export const sendNotification = async(data)=>{


    try{


        const response = await api.post(

            "/notifications/send/",

            data

        );


        return response;


    }


    catch(error){


        console.error(

            "SEND NOTIFICATION ERROR:",

            error.response?.data
            ||
            error.message

        );


        throw error;


    }


};







// =====================================================
// STUDENT NOTIFICATIONS
// GET /api/student/notifications/
// =====================================================

export const getStudentNotifications = async()=>{


    try{


        const response = await api.get(

            "/student/notifications/"

        );


        return response;


    }


    catch(error){


        console.error(

            "STUDENT NOTIFICATION ERROR:",

            error.response?.data
            ||
            error.message

        );


        throw error;


    }


};







// =====================================================
// COMPANY NOTIFICATIONS
// GET /api/company/notifications/
// =====================================================

export const getCompanyNotifications = async()=>{


    try{


        const response = await api.get(

            "/company/notifications/"

        );


        return response;


    }


    catch(error){


        console.error(

            "COMPANY NOTIFICATION ERROR:",

            error.response?.data
            ||
            error.message

        );


        throw error;


    }


};







// =====================================================
// NOTIFICATION HELPER
// =====================================================


export const formatNotification = (notification)=>{


    return {


        id:
        notification.id,


        title:
        notification.title
        ||
        "Notification",



        message:
        notification.message
        ||
        "",



        is_read:
        notification.is_read
        ||
        false,



        created_at:
        notification.created_at
        ||
        notification.date



    };


};