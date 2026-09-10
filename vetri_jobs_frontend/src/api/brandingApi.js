import api from "./axios";


export const getSiteBranding = async()=>{

    try{

        return await api.get("/site-branding/");

    }

    catch(error){

        console.error(
            "SITE BRANDING ERROR:",
            error.response?.data || error.message
        );

        throw error;

    }

};


export default { getSiteBranding };
