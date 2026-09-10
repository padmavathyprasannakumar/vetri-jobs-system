import React from "react";


import "./Loader.css";





function Loader({

    text="Loading..."

}){



    return (



        <div className="loader-container">







            <div className="loader-spinner">



                <div className="spinner-circle"></div>



            </div>







            <p className="loader-text">


                {text}


            </p>







        </div>


    );


}



export default Loader;