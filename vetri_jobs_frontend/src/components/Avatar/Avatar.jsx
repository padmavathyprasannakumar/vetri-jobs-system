import React from "react";

import "./Avatar.css";




// Deterministic color per name, so the same person always gets the same color.
const PALETTE = [
    "#4338ca", "#0f766e", "#b45309", "#be185d",
    "#0369a1", "#15803d", "#7c3aed", "#c2410c",
];

const colorForName = (name)=>{

    if(!name) return PALETTE[0];

    let hash = 0;

    for(let i=0; i<name.length; i++){
        hash = name.charCodeAt(i) + ((hash << 5) - hash);
    }

    return PALETTE[Math.abs(hash) % PALETTE.length];

};

const initialsForName = (name)=>{

    if(!name) return "?";

    return name
        .trim()
        .split(/\s+/)
        .map(w=>w.charAt(0))
        .join("")
        .slice(0, 2)
        .toUpperCase();

};




// name: full name used for initials + color. photoUrl: optional real photo.
// size: pixel size (default 44). className: extra class for the wrapper.
const Avatar = ({ name, photoUrl, size = 44, className = "" })=>{

    if(photoUrl){
        return(
            <img
            src={photoUrl}
            alt={name || "Profile"}
            className={"avatar-photo " + className}
            style={{ width: size, height: size }}
            />
        );
    }

    return(

        <div
        className={"avatar-initials " + className}
        style={{
            width: size,
            height: size,
            background: colorForName(name),
            fontSize: Math.max(12, size * 0.4),
        }}
        title={name || ""}
        >
            {initialsForName(name)}
        </div>

    );

};


export default Avatar;
