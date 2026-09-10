import React, {

    useEffect,

    useState

} from "react";


import { getSiteBranding } from "../../api/brandingApi";


// Fetched once per page load and shared across every
// instance of this component (navbar + all 4 dashboard
// sidebars), instead of one API call per sidebar. Expires
// quickly so that uploading a new logo/image in Django Admin
// shows up on the next navigation without needing users to
// fully close and reopen their browser tab.

let cachedBranding = null;

let cachedAt = 0;

let pendingFetch = null;

const CACHE_TTL_MS = 15000;


const fetchBranding = ()=>{

    const isFresh = cachedBranding && (Date.now() - cachedAt < CACHE_TTL_MS);

    if(isFresh){

        return Promise.resolve(cachedBranding);

    }

    if(!pendingFetch){

        pendingFetch = getSiteBranding()
            .then(res=>{

                cachedBranding = res.data;

                cachedAt = Date.now();

                pendingFetch = null;

                return cachedBranding;

            })
            .catch(()=>{

                cachedBranding = cachedBranding || {
                    site_name:"Vetri Jobs",
                    tagline:"Career Portal",
                    logo_url:null,
                };

                cachedAt = Date.now();

                pendingFetch = null;

                return cachedBranding;

            });

    }

    return pendingFetch;

};




const BrandLogo = ({

    onClick,

    showTagline = true,

    customTagline,

    circleClassName = "logo-circle",

    wrapperClassName = "navbar-logo"

})=>{


    const [branding,setBranding] = useState(

        cachedBranding || {
            site_name:"Vetri Jobs",
            tagline:"Career Portal",
            logo_url:null,
        }

    );


    useEffect(()=>{

        let mounted = true;

        fetchBranding().then(data=>{

            if(mounted) setBranding(data);

        });

        return ()=>{ mounted = false; };

    },[]);




    return(

        <div

        className={wrapperClassName}

        onClick={onClick}

        style={onClick ? {cursor:"pointer"} : undefined}

        >


            <div className={circleClassName}>

                {
                branding.logo_url ?

                <img

                src={branding.logo_url}

                alt={branding.site_name}

                style={{

                    width:"100%",

                    height:"100%",

                    objectFit:"cover",

                    borderRadius:"inherit",

                }}

                />

                :

                (branding.site_name || "Vetri Jobs")
                    .split(" ")
                    .map(w=>w.charAt(0))
                    .join("")
                    .slice(0,2)
                    .toUpperCase()
                }

            </div>


            <div>

                <h2>

                    {branding.site_name || "Vetri Jobs"}

                </h2>


                {
                showTagline &&

                <span>

                    {customTagline || branding.tagline || "Career Portal"}

                </span>
                }

            </div>


        </div>

    );

};


export default BrandLogo;
