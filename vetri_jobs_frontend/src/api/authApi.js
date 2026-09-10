// =====================================================
// AUTH API
// Vetri Jobs Frontend
// Django REST Framework Backend
// =====================================================


import api from "./axios";




// =====================================================
// REGISTER USER
// POST /api/auth/register/
// =====================================================


export const registerUser = async(data)=>{


    try{


        const response = await api.post(

            "auth/register/",

            data

        );


        return response;


    }


    catch(error){


        console.error(

            "REGISTER ERROR:",

            error.response?.data
            ||
            error.message

        );


        throw error;


    }


};


export const registerCompany = async(formData)=>{

    try{

        const response = await api.post(
            "company/register/",
            formData,
            {
                headers: {
                    "Content-Type": "multipart/form-data",
                },
            }
        );

        return response;

    }

    catch(error){

        console.error(
            "COMPANY REGISTER ERROR:",
            error.response?.data || error.message
        );

        throw error;

    }

};


export const checkCompanyApplicationStatus = async(data)=>{

    try{

        const response = await api.post(
            "company/application-status/",
            data
        );

        return response;

    }

    catch(error){

        console.error(
            "CHECK APPLICATION STATUS ERROR:",
            error.response?.data || error.message
        );

        throw error;

    }

};


export const requestPasswordReset = async(email)=>{

    try{

        const response = await api.post(
            "auth/forgot-password/",
            { email }
        );

        return response;

    }

    catch(error){

        console.error(
            "FORGOT PASSWORD ERROR:",
            error.response?.data || error.message
        );

        throw error;

    }

};


export const confirmPasswordReset = async(data)=>{

    try{

        const response = await api.post(
            "auth/reset-password-confirm/",
            data
        );

        return response;

    }

    catch(error){

        console.error(
            "RESET PASSWORD CONFIRM ERROR:",
            error.response?.data || error.message
        );

        throw error;

    }

};










// =====================================================
// LOGIN USER
// POST /api/auth/login/
// =====================================================


export const loginUser = async(data)=>{


    try{


        const response = await api.post(


            "auth/login/",


            data


        );





        saveAuthData(

            response.data

        );





        return response;



    }


    catch(error){



        console.error(


            "LOGIN ERROR:",


            error.response?.data
            ||
            error.message


        );



        throw error;



    }



};









// =====================================================
// GET CURRENT USER
// GET /api/auth/me/
// =====================================================


export const getCurrentUser = async()=>{


    try{


        const response = await api.get(


            "auth/me/"


        );





        if(response.data){


            localStorage.setItem(


                "user",


                JSON.stringify(

                    response.data

                )


            );


        }





        return response;



    }


    catch(error){



        console.error(


            "CURRENT USER ERROR:",


            error.response?.data
            ||
            error.message


        );



        throw error;



    }



};









// =====================================================
// LOGOUT USER
// POST /api/auth/logout/
// =====================================================


export const logoutUser = async()=>{


    try{


        const response = await api.post(


            "auth/logout/"


        );



        clearAuthData();



        return response;



    }


    catch(error){



        console.error(


            "LOGOUT ERROR:",


            error.response?.data
            ||
            error.message


        );



        clearAuthData();



        return null;



    }



};









// =====================================================
// REFRESH TOKEN
// POST /api/token/refresh/
// =====================================================


export const refreshToken = async()=>{


    try{


        const refresh =

        localStorage.getItem(

            "refresh_token"

        );





        if(!refresh){


            return null;


        }






        const response = await api.post(


            "token/refresh/",


            {


                refresh


            }


        );





        const access =

        response.data.access;







        if(access){



            localStorage.setItem(


                "access_token",


                access


            );



        }





        return access;



    }


    catch(error){



        clearAuthData();



        return null;



    }



};









// =====================================================
// UPDATE PROFILE
// PUT /api/profile/update/
// =====================================================


export const updateProfile = async(data)=>{


    try{


        return await api.put(


            "profile/update/",


            data


        );



    }


    catch(error){



        console.error(


            "PROFILE UPDATE ERROR:",


            error.response?.data
            ||
            error.message


        );



        throw error;



    }



};









// =====================================================
// SAVE AUTH DATA
// =====================================================


export const saveAuthData=(data)=>{



    if(!data){


        return;


    }







    const access =

        data.access

        ||

        data.tokens?.access

        ||

        data.token;







    const refresh =

        data.refresh

        ||

        data.tokens?.refresh;








    const user =

        data.user

        ||

        data.profile

        ||

        null;









    if(access){


        localStorage.setItem(


            "access_token",


            access


        );


    }







    if(refresh){



        localStorage.setItem(


            "refresh_token",


            refresh


        );


    }








    if(user){



        localStorage.setItem(


            "user",


            JSON.stringify(

                normalizeUser(user)

            )


        );



    }



};









// =====================================================
// NORMALIZE USER
// =====================================================


export const normalizeUser=(user)=>{


    if(!user){


        return null;


    }





    return {


        ...user,


        role:


        String(

            user.role || ""

        )

        .trim()

        .toLowerCase()



    };



};









// =====================================================
// CLEAR AUTH DATA
// =====================================================


export const clearAuthData=()=>{


    localStorage.removeItem(


        "access_token"


    );


    localStorage.removeItem(


        "refresh_token"


    );


    localStorage.removeItem(


        "user"


    );


};









// =====================================================
// GET STORED USER
// =====================================================


export const getStoredUser=()=>{


    try{


        const user =

        localStorage.getItem(

            "user"

        );





        return user

        ?

        JSON.parse(user)

        :

        null;



    }


    catch(error){



        return null;



    }



};









// =====================================================
// GET ROLE
// =====================================================


export const getUserRole=()=>{


    const user =

    getStoredUser();





    return user?.role || null;



};









// =====================================================
// ROLE CHECKERS
// =====================================================


export const isStudent=()=>{


    return getUserRole()

    ===

    "student";


};





export const isCompany=()=>{


    return getUserRole()

    ===

    "company";


};





export const isPlacementAdmin=()=>{


    return getUserRole()

    ===

    "placement_admin";


};





export const isSuperAdmin=()=>{


    return getUserRole()

    ===

    "super_admin";


};









// =====================================================
// DASHBOARD ROUTER
// =====================================================


export const getDashboardPath=()=>{


    const role =

    getUserRole();





    switch(role){



        case "student":


            return "/student/dashboard";





        case "company":


            return "/company/dashboard";





        case "placement_admin":


            return "/placement/dashboard";





        case "super_admin":


            return "/";





        default:


            return "/student/login";



    }



};









// =====================================================
// CHECK LOGIN
// =====================================================


export const isAuthenticated=()=>{


    return Boolean(


        localStorage.getItem(

            "access_token"

        )


    );


};









// =====================================================
// DEFAULT EXPORT
// =====================================================


export default {



    registerUser,

    loginUser,

    logoutUser,

    getCurrentUser,

    updateProfile,

    refreshToken,

    saveAuthData,

    clearAuthData,

    getStoredUser,

    getUserRole,

    getDashboardPath,

    isStudent,

    isCompany,

    isPlacementAdmin,

    isSuperAdmin,

    isAuthenticated,

    normalizeUser


};