#!/bin/bash
#
# NAME
#
#   make
#
# SYNPOSIS
#
#   make
#
# DESC
# 
#   'make' sets up a pfcon instance using docker-compose. It can also
#   optionally populate a swift container with sample data.
#
# ARGS
#
#       


source ./decorate.sh 

declare -i STEP=0
RESTART=""
HERE=$(pwd)
echo "Starting script in dir $HERE"

declare -a A_CONTAINER=(
    "pfcon${TAG}"
    "docker-swift-onlyone"
)

CREPO=fnndsc
TAG=:dev

if [[ -f .env ]] ; then
    source .env 
fi

while getopts "r:psidUIa:S:" opt; do
    case $opt in 
        r) b_restart=1
           RESTART=$OPTARG                      ;;
        p) b_pause=1                            ;;
        s) b_skipIntro=1                        ;;
        i) b_norestartinteractive_chris_dev=1   ;;
        a) b_swarmAdvertiseAdr=1
            SWARMADVERTISEADDR=$OPTARG          ;;
        d) b_debug=1                            ;;
        U) b_skipUnitTests=1                    ;;
        I) b_skipIntegrationTests=1             ;;
        S) b_storeBaseOverride=1
           STOREBASE=$OPTARG                    ;;
    esac
done

shift $(($OPTIND - 1))
if (( $# == 1 )) ; then
    REPO=$1
    export CREPO=$(echo $REPO | awk -F \: '{print $1}')
    export TAG=$(echo $REPO | awk -F \: '{print $2}')
    if (( ${#TAG} )) ; then
        TAG=":$TAG"
    fi
fi

title -d 1 "Setting global exports..."
    if (( ! b_storeBaseOverride )) ; then
        if [[ ! -d FS/remote ]] ; then
            mkdir -p FS/remote
        fi
        cd FS/remote
        STOREBASE=$(pwd)
        cd $HERE
    fi
    echo -e "${STEP}.1 For pman override to swarm containers, exporting\n\tSTOREBASE=$STOREBASE... "
    export STOREBASE=$STOREBASE
    if (( b_debug )) ; then
        echo -e "${STEP}.2 Setting debug quiet to OFF. Note this is noisy!"
        export CHRIS_DEBUG_QUIET=0
    fi
windowBottom

if (( b_restart )) ; then
    docker-compose stop ${RESTART}_service && docker-compose rm -f ${RESTART}_service
    docker-compose run --service-ports ${RESTART}_service
else
    title -d 1 "Using <$CREPO> family containers..."
    if (( ! b_skipIntro )) ; then 
    if [[ $CREPO == "fnndsc" ]] ; then
            echo "Pulling latest version of all containers..."
            for CONTAINER in ${A_CONTAINER[@]} ; do
                echo ""
                CMD="docker pull ${CREPO}/$CONTAINER"
                echo -e "\t\t\t${White}$CMD${NC}"
                echo $sep
                echo $CMD | sh
                echo $sep
            done
        fi
    fi
    windowBottom

    if (( ! b_skipIntro )) ; then 
        title -d 1 "Will use containers with following version info:"
        for CONTAINER in ${A_CONTAINER[@]} ; do
            if [[   $CONTAINER != "chris_dev_backend"   && \
                    $CONTAINER != "pl-pacsretrieve"     && \
                    $CONTAINER != "pl-pacsquery"        && \
                    $CONTAINER != "docker-swift-onlyone"     && \
                    $CONTAINER != "swarm" ]] ; then
                CMD="docker run ${CREPO}/$CONTAINER --version"
                printf "${White}%40s\t\t" "${CREPO}/$CONTAINER"
                Ver=$(echo $CMD | sh | grep Version)
                echo -e "$Green$Ver"
            fi
        done
        # Determine the versions of pfurl *inside* pfcon/chris_dev_backend/pl-pacs*
        CMD="docker run --entrypoint /usr/local/bin/pfurl ${CREPO}/pfcon${TAG} --version"
        printf "${White}%40s\t\t" "pfurl inside ${CREPO}/pfcon${TAG}"
        Ver=$(echo $CMD | sh | grep Version)
        echo -e "$Green$Ver"
        windowBottom
    fi

    title -d 1 "Shutting down any running pfcon and pfcon related containers... "
    docker-compose stop
    docker-compose rm -vf
    for CONTAINER in ${A_CONTAINER[@]} ; do
        printf "%30s" "$CONTAINER"
        docker ps -a                                                        |\
            grep $CONTAINER                                                 |\
            awk '{printf("docker stop %s && docker rm -vf %s\n", $1, $1);}' |\
            sh >/dev/null
        printf "${Green}%20s${NC}\n" "done"
    done
    windowBottom

    title -d 1 "Starting pfcon containerized development environment using " " ./docker-compose.yml"
    echo "docker-compose up -d"
    docker-compose up -d
    windowBottom
    if (( !  b_norestartinteractive_chris_dev )) ; then
        title -d 1 "Restarting pfcon development container in interactive mode..."
        docker-compose stop pfcon_dev
        docker-compose rm -f pfcon_dev
        docker-compose run --service-ports pfcon_dev
        echo ""
        windowBottom
    fi
fi
