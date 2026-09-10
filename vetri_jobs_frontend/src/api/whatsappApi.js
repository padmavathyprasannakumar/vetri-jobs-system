// =====================================================
// WHATSAPP API
// Vetri Jobs WhatsApp Integration
// =====================================================


import api from "./axios";






// =====================================================
// SEND WHATSAPP MESSAGE
// POST /api/whatsapp/send/
// =====================================================
//
// Example:
//
// {
//    phone_number:"+91123456789",
//    message:"Your interview is scheduled"
// }
//
// =====================================================


export const sendWhatsAppMessage = async(data)=>{


    try{


        return await api.post(

            "/whatsapp/send/",

            data

        );


    }


    catch(error){


        console.error(

            "SEND WHATSAPP ERROR:",

            error.response?.data
            ||
            error.message

        );


        throw error;


    }


};









// =====================================================
// SEND STUDENT WHATSAPP
// =====================================================


export const sendStudentWhatsApp = async(

studentId,

message

)=>{


    try{


        return await api.post(

            "/whatsapp/send/",

            {


                student_id:
                studentId,


                message:
                message


            }


        );


    }


    catch(error){


        console.error(

            "STUDENT WHATSAPP ERROR:",

            error.response?.data
            ||
            error.message

        );


        throw error;


    }


};









// =====================================================
// SEND COMPANY WHATSAPP
// =====================================================


export const sendCompanyWhatsApp = async(

companyId,

message

)=>{


    try{


        return await api.post(

            "/whatsapp/send/",

            {


                company_id:
                companyId,


                message:
                message


            }


        );


    }


    catch(error){


        console.error(

            "COMPANY WHATSAPP ERROR:",

            error.response?.data
            ||
            error.message

        );


        throw error;


    }


};









// =====================================================
// SEND BULK WHATSAPP
// ADMIN / PLACEMENT
// =====================================================


export const sendBulkWhatsApp = async(data)=>{


    try{


        return await api.post(

            "/whatsapp/send/bulk/",

            data

        );


    }


    catch(error){


        console.error(

            "BULK WHATSAPP ERROR:",

            error.response?.data
            ||
            error.message

        );


        throw error;


    }


};









// =====================================================
// GET WHATSAPP SETTINGS
// GET /api/whatsapp/settings/
// =====================================================


export const getWhatsAppSettings = async()=>{


    try{


        return await api.get(

            "/whatsapp/settings/"

        );


    }


    catch(error){


        console.error(

            "GET WHATSAPP SETTINGS ERROR:",

            error.response?.data
            ||
            error.message

        );


        throw error;


    }


};









// =====================================================
// UPDATE WHATSAPP SETTINGS
// PUT /api/whatsapp/settings/
// =====================================================


export const updateWhatsAppSettings = async(data)=>{


    try{


        return await api.put(

            "/whatsapp/settings/",

            data

        );


    }


    catch(error){


        console.error(

            "UPDATE WHATSAPP SETTINGS ERROR:",

            error.response?.data
            ||
            error.message

        );


        throw error;


    }


};









// =====================================================
// GET WHATSAPP MESSAGE HISTORY
// GET /api/whatsapp/messages/
// =====================================================


export const getWhatsAppMessages = async()=>{


    try{


        return await api.get(

            "/whatsapp/messages/"

        );


    }


    catch(error){


        console.error(

            "WHATSAPP HISTORY ERROR:",

            error.response?.data
            ||
            error.message

        );


        throw error;


    }


};









// =====================================================
// GET SINGLE WHATSAPP MESSAGE
// =====================================================


export const getWhatsAppMessage = async(id)=>{


    try{


        return await api.get(

            `/whatsapp/messages/${id}/`

        );


    }


    catch(error){


        console.error(

            "GET WHATSAPP MESSAGE ERROR:",

            error.response?.data
            ||
            error.message

        );


        throw error;


    }


};









// =====================================================
// DELETE WHATSAPP MESSAGE
// =====================================================


export const deleteWhatsAppMessage = async(id)=>{


    try{


        return await api.delete(

            `/whatsapp/messages/${id}/`

        );


    }


    catch(error){


        console.error(

            "DELETE WHATSAPP MESSAGE ERROR:",

            error.response?.data
            ||
            error.message

        );


        throw error;


    }


};









// =====================================================
// CHECK WHATSAPP CONNECTION STATUS
// =====================================================


export const checkWhatsAppStatus = async()=>{


    try{


        return await api.get(

            "/whatsapp/status/"

        );


    }


    catch(error){


        console.error(

            "WHATSAPP STATUS ERROR:",

            error.response?.data
            ||
            error.message

        );


        throw error;


    }


};









// =====================================================
// MESSAGE TEMPLATE MANAGEMENT
// =====================================================


export const getWhatsAppTemplates = async()=>{


    try{


        return await api.get(

            "/whatsapp/templates/"

        );


    }


    catch(error){


        console.error(

            "GET TEMPLATE ERROR:",

            error.response?.data
            ||
            error.message

        );


        throw error;


    }


};








export const createWhatsAppTemplate = async(data)=>{


    return await api.post(

        "/whatsapp/templates/",

        data

    );


};








export const updateWhatsAppTemplate = async(id,data)=>{


    return await api.put(

        `/whatsapp/templates/${id}/`,

        data

    );


};








export const deleteWhatsAppTemplate = async(id)=>{


    return await api.delete(

        `/whatsapp/templates/${id}/`

    );


};









// =====================================================
// FORMAT WHATSAPP STATUS
// =====================================================


export const formatWhatsAppStatus=(data)=>{


    return {


        connected:

            data.connected
            ||
            false,


        phone:

            data.phone
            ||
            "",



        provider:

            data.provider
            ||
            "WhatsApp API"



    };


};









export default {


    sendWhatsAppMessage,


    sendStudentWhatsApp,


    sendCompanyWhatsApp,


    sendBulkWhatsApp,


    getWhatsAppSettings,


    updateWhatsAppSettings,


    getWhatsAppMessages,


    getWhatsAppMessage,


    deleteWhatsAppMessage,


    checkWhatsAppStatus,


    getWhatsAppTemplates,


    createWhatsAppTemplate,


    updateWhatsAppTemplate,


    deleteWhatsAppTemplate,


    formatWhatsAppStatus


};