graph TD
    %% Sources de contenu
    subgraph "SOURCES (Création)"
        YT_Chan[YouTube @LCDMH]
        Fuji[Fujifilm X-H2S / iPhone]
        WebForm[Interface Mobile LCDMH]
    end

    %% Cerveaux de traitement
    subgraph "AUTOMATISATION (Le Moteur)"
        GH_Actions[GitHub Actions]
        Make_Hub[Make.com]
        Cloudinary[Cloudinary API]
    end

    %% Destinations
    subgraph "HUBS & RÉSEAUX (Diffusion)"
        Site[LCDMH.com - GitHub Pages]
        FB[Facebook Page]
        IG[Instagram Business]
        PIN[Pinterest - Boards thématiques]
    end

    %% Flux YouTube
    YT_Chan -->|Daily Sync| GH_Actions
    GH_Actions -->|Update JSON Data| Site
    Site -->|Weekly Post| Make_Hub
    Make_Hub -->|Auto-Publish| FB

    %% Flux Live Roadtrip
    Fuji --> WebForm
    WebForm -->|Upload Brute| Cloudinary
    Cloudinary -->|Transformation 1:1 Carré| Make_Hub
    Make_Hub -->|Carousel Post| IG
    Make_Hub -->|Condition: Both| FB
    Make_Hub -->|New Branch| PIN

    %% Maillage SEO
    IG -->|Lien Bio| Site
    FB -->|Lien Post| Site
    Site -->|Backlink| YT_Chan