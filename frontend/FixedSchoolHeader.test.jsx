import React from "react";
import {render, screen, fireEvent, within, cleanup} from "@testing-library/react";
import {afterEach, describe, expect, it, vi} from "vitest";
import {BrandContext, Shell, PageHeader} from "./yem-ui.jsx";

afterEach(cleanup);

describe("En-tête fixe des établissements",()=>{
  it("affiche l'identité configurée une seule fois et permet de rechercher les modules autorisés",()=>{
    const navigate=vi.fn();
    const brand={fixedHeader:true,name:"École test",city:"Libreville",logo:"/logo-test",banner:"/banner-test"};
    render(<BrandContext.Provider value={brand}>
      <Shell nav={[["dashboard","home","Tableau de bord"],["payments","card","Paiements"]]} onNavigate={navigate}>
        <PageHeader title="Tableau de bord" subtitle="Pilotage"/>
      </Shell>
    </BrandContext.Provider>);
    const header=screen.getByRole("banner");
    expect(within(header).getByLabelText("Identité de l'établissement")).toBeTruthy();
    expect(screen.getAllByAltText("Logo de l'établissement")).toHaveLength(1);
    expect(within(header).getByAltText("Logo de l'établissement").getAttribute("src")).toBe("/logo-test");
    fireEvent.click(screen.getByRole("button",{name:"Rechercher dans les modules"}));
    const input=screen.getByRole("textbox",{name:"Rechercher un module"});
    fireEvent.change(input,{target:{value:"paiement"}});
    const popup=header.querySelector(".yd-compact-search-panel");
    expect(within(popup).queryByRole("button",{name:"Tableau de bord"})).toBeNull();
    fireEvent.click(within(popup).getByRole("button",{name:"Paiements"}));
    expect(navigate).toHaveBeenCalledWith("payments");
    expect(screen.queryByRole("textbox",{name:"Rechercher un module"})).toBeNull();
  });

  it("ouvre et referme la loupe au clavier, sans modifier les autres espaces",()=>{
    render(<BrandContext.Provider value={{fixedHeader:true,name:"École test"}}>
      <Shell nav={[]}><PageHeader title="Accueil"/></Shell>
    </BrandContext.Provider>);
    const search=screen.getByRole("button",{name:"Rechercher dans les modules"});
    fireEvent.click(search);
    fireEvent.keyDown(screen.getByRole("textbox",{name:"Rechercher un module"}),{key:"Escape"});
    expect(search.getAttribute("aria-expanded")).toBe("false");
    cleanup();
    render(<Shell nav={[]}><PageHeader title="Démo"/></Shell>);
    expect(screen.queryByRole("button",{name:"Rechercher dans les modules"})).toBeNull();
  });
});
