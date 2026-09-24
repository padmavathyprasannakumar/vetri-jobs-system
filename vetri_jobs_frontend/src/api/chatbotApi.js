// =====================================================
// CHATBOT API
// Vetri Jobs AI Assistant
// =====================================================


import api from "./axios";





// =====================================================
// SEND CHAT MESSAGE
// POST /api/chatbot/
// =====================================================
//
// Request:
//
// {
//    message:"How to apply job?",
//    page_context:{ page:"student/jobs", job_id:12 }   // optional
// }
//
// Response:
//
// {
//    reply:"You can apply...",
//    refresh:["applications","dashboard"]              // optional
// }
//
// page_context tells the assistant where the student currently is,
// so "apply to this job" works without naming the job.
//
// =====================================================


export const sendChatMessage = async(message, file, pageContext)=>{


    try{


        // The floating widget calls this as sendChatMessage({message}),
        // while other callers might just pass a plain string - accept
        // both so the request body is always a clean {message: "..."}.

        const text =
            typeof message === "string"
                ? message
                : message?.message ?? "";


        // When an attachment is included (resume upload via chat),
        // send multipart/form-data instead of plain JSON.

        if(file){

            const formData = new FormData();

            formData.append("message", text);

            formData.append("attachment", file);

            // multipart can't carry a nested object, so it goes as a
            // JSON string - the backend parses it back.

            if(pageContext){

                formData.append(
                    "page_context",
                    JSON.stringify(pageContext)
                );

            }


            const response = await api.post(

                "/chatbot/",

                formData,

                {
                    headers:{
                        "Content-Type":
                        "multipart/form-data"
                    }
                }

            );


            return response;

        }


        const response = await api.post(

            "/chatbot/",

            {

                message: text,

                ...(pageContext ? { page_context: pageContext } : {})

            }


        );


        return response;



    }


    catch(error){


        console.error(

            "CHATBOT MESSAGE ERROR:",

            error.response?.data
            ||
            error.message


        );


        throw error;


    }


};








// =====================================================
// SEND CHAT WITH FULL DATA
// =====================================================
//
// Used when you need:
//
// - user id
// - session id
// - role
//
// =====================================================


export const sendChatRequest = async(data)=>{


    try{


        const response = await api.post(

            "/chatbot/",

            data


        );



        return response;



    }


    catch(error){


        console.error(

            "CHATBOT REQUEST ERROR:",

            error.response?.data
            ||
            error.message


        );


        throw error;


    }


};








// =====================================================
// GET CHAT HISTORY
// GET /api/chatbot/history/
// =====================================================


export const getChatHistory = async()=>{


    try{


        const response = await api.get(

            "/chatbot/history/"

        );


        return response;



    }


    catch(error){


        console.error(

            "CHAT HISTORY ERROR:",

            error.response?.data
            ||
            error.message


        );


        throw error;


    }


};








// =====================================================
// CLEAR CHAT HISTORY
// DELETE /api/chatbot/history/
// =====================================================


export const clearChatHistory = async()=>{


    try{


        const response = await api.delete(

            "/chatbot/history/"

        );


        return response;



    }


    catch(error){


        console.error(

            "CLEAR CHAT HISTORY ERROR:",

            error.response?.data
            ||
            error.message


        );


        throw error;


    }


};








// =====================================================
// CHATBOT HEALTH CHECK
// GET /api/chatbot/status/
// =====================================================


export const chatbotStatus = async()=>{


    try{


        const response = await api.get(

            "/chatbot/status/"

        );


        return response;



    }


    catch(error){


        console.error(

            "CHATBOT STATUS ERROR:",

            error.response?.data
            ||
            error.message


        );


        throw error;


    }


};








// =====================================================
// FORMAT RESPONSE
// =====================================================


export const formatChatResponse=(data)=>{


    return {


        reply:

            data.reply
            ||
            data.message
            ||
            "Sorry, I could not understand.",



        timestamp:

            data.timestamp
            ||
            new Date()



    };


};







export default {


    sendChatMessage,

    sendChatRequest,

    getChatHistory,

    clearChatHistory,

    chatbotStatus,

    formatChatResponse


};
