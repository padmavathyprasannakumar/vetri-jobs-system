// =====================================================
// AXIOS CONFIGURATION
// Vetri Jobs Frontend
// Django REST Framework Backend
// =====================================================


import axios from "axios";




// In production, set VITE_API_URL in your host's env vars (e.g.
// Vercel project settings) to your deployed backend's URL, e.g.
// https://your-app-name.onrender.com/api/
// Falls back to localhost so local development needs no setup.
const API_BASE_URL =
    import.meta.env.VITE_API_URL || "http://localhost:8000/api/";




// =====================================================
// API INSTANCE
// =====================================================


const api = axios.create({

    baseURL:

        API_BASE_URL,


    timeout:

        15000,


    headers:{

        "Accept":

            "application/json",

    },

});






// =====================================================
// LOGOUT HELPER
// =====================================================


const logout = ()=>{


    // The standalone /student/login, /company/login and
    // /placement/login pages were retired - they now just
    // client-side redirect back to "/". Pointing this hard
    // redirect at those URLs created a redirect loop (hard
    // reload -> client redirect to "/" -> another 401 ->
    // hard reload again), which showed up as the page
    // rapidly blinking. Sending everyone straight to "/"
    // (which now hosts the login widget for student/company/
    // placement_admin) avoids that. The super_admin React
    // pages and /admin/login have been removed entirely -
    // super admin tasks are handled through Django admin
    // instead - so there's no separate page left to send
    // that role to either.

    const loginPath = "/";


    localStorage.removeItem(
        "access_token"
    );


    localStorage.removeItem(
        "refresh_token"
    );


    localStorage.removeItem(
        "user"
    );



    if(
        window.location.pathname !==
        loginPath
    ){

        window.location.href =
            loginPath;

    }

};







// =====================================================
// REQUEST INTERCEPTOR
// ADD JWT TOKEN
// =====================================================


api.interceptors.request.use(


(config)=>{


    // Never attach a (possibly stale/expired) access token to
    // login/register/refresh calls. DRF's JWTAuthentication
    // validates the Authorization header BEFORE the view's
    // AllowAny permission is even checked - so an old token
    // left over from a previous session causes these public
    // endpoints to fail with 401 even though they don't
    // require auth at all. This was the actual cause of
    // "login worked once, then stopped working with the same
    // credentials": a leftover/expired token from the first
    // session was being sent along with every later login
    // attempt.

    const PUBLIC_AUTH_PATHS = [
        "auth/login",
        "auth/register",
        "auth/logout",
        "token/refresh",
    ];

    const isPublicAuthCall = PUBLIC_AUTH_PATHS.some(path=>

        (config.url || "").includes(path)

    );


    const token =

        isPublicAuthCall

        ? null

        : localStorage.getItem(
            "access_token"
        );



    if(token){


        config.headers.Authorization =

        `Bearer ${token}`;


    }







    // ==============================
    // HANDLE FILE UPLOAD
    // ==============================


    if(config.data instanceof FormData){


        config.headers[

            "Content-Type"

        ] =

        "multipart/form-data";


    }


    else{


        config.headers[

            "Content-Type"

        ] =

        "application/json";


    }






    return config;



},



(error)=>{


    return Promise.reject(error);


}



);









// =====================================================
// REFRESH TOKEN QUEUE
// =====================================================


let isRefreshing = false;


let failedQueue=[];




const processQueue = (

error,

token=null

)=>{


    failedQueue.forEach(

        promise=>{


            if(error){

                promise.reject(error);

            }

            else{

                promise.resolve(token);

            }


        }

    );


    failedQueue=[];


};








// =====================================================
// RESPONSE INTERCEPTOR
// AUTO REFRESH JWT
// =====================================================


api.interceptors.response.use(


(response)=>{


    return response;


},



async(error)=>{


    const originalRequest =
        error.config;




    if(!originalRequest){

        return Promise.reject(error);

    }



    if(!error.response){

        return Promise.reject(error);

    }







    const publicRoutes=[


        "auth/register/",


        "auth/login/",


        "token/refresh/",


        "company/register/",


        "company/application-status/",


        "auth/forgot-password/",


        "auth/reset-password-confirm/"


    ];





    const isPublicRoute =

    publicRoutes.some(

        route=>

        originalRequest.url.includes(
            route
        )

    );






    if(isPublicRoute){


        return Promise.reject(error);


    }









    if(

        error.response.status === 401

        &&

        !originalRequest._retry

    ){



        originalRequest._retry=true;




        const refreshToken =

        localStorage.getItem(
            "refresh_token"
        );




        if(!refreshToken){


            console.log(
                "NO REFRESH TOKEN"
            );


            logout();


            return Promise.reject(error);


        }





        if(isRefreshing){


            return new Promise(

                (resolve,reject)=>{


                    failedQueue.push({

                        resolve,

                        reject

                    });


                }

            )

            .then(token=>{


                originalRequest.headers.Authorization =

                `Bearer ${token}`;


                return api(
                    originalRequest
                );


            });


        }






        isRefreshing=true;






        try{


            const response =

            await axios.post(


            `${API_BASE_URL}token/refresh/`,


            {

                refresh:
                refreshToken

            }


            );





            const newAccessToken =

            response.data.access;






            localStorage.setItem(

                "access_token",

                newAccessToken

            );







            api.defaults.headers.common.Authorization =

            `Bearer ${newAccessToken}`;






            processQueue(

                null,

                newAccessToken

            );






            originalRequest.headers.Authorization =

            `Bearer ${newAccessToken}`;






            return api(
                originalRequest
            );






        }


        catch(refreshError){



            processQueue(

                refreshError,

                null

            );


            logout();


            return Promise.reject(
                refreshError
            );



        }



        finally{


            isRefreshing=false;


        }



    }








    if(error.response.status===403){


        console.warn(
            "Permission denied"
        );


    }






    if(error.response.status===404){


        console.warn(
            "API endpoint not found"
        );


    }





    return Promise.reject(error);



}



);








export default api;