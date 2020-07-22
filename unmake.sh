#!/bin/bash

source ./decorate.sh

declare -i STEP=0

title -d 1 "Destroying pfcon containerized development environment" \
                    "from  ./docker-compose_dev.yml"

    echo "Do you want to stop and rm all containers? [y/n]"                 | ./boxes.sh
    windowBottom
    old_stty_cfg=$(stty -g)
    stty raw -echo ; REPLY=$(head -c 1) ; stty $old_stty_cfg
    echo -en "\033[2A\033[2K"
    windowBottom
    if [[ $REPLY =~ ^[Yy]$ ]] ; then

        title -d 1 "Stopping services..."
            echo "This might take a few minutes... please be patient."      | ./boxes.sh ${Yellow}
            windowBottom
            docker-compose -f docker-compose_dev.yml --no-ansi stop >& dc.out
            echo -en "\033[2A\033[2K"
            cat dc.out | sed -E 's/(.{80})/\1\n/g'                          | ./boxes.sh ${LightBlue}
        windowBottom

        title -d 1 "Removing all containers..."
            echo "This might take a few minutes... please be patient."      | ./boxes.sh ${Yellow}
            windowBottom
            docker-compose -f docker-compose_dev.yml --no-ansi rm -vf >& dc.out
            echo -en "\033[2A\033[2K"
            cat dc.out | sed -E 's/(.{80})/\1\n/g'                          | ./boxes.sh ${LightBlue}
        windowBottom

        title -d 1 "Removing any orphans..."
            a_VOLS=(
                "pfcon_swift_storage"
                "pman"
                "pfioh"
                "/pfcon"
            )
            a_PVOLS=()
            for vol in ${a_VOLS[@]}; do
                DOCKERPS=$(docker ps -a | grep -v CONTAINER | grep $vol)
                DOCKERVOLNAME=$(echo $DOCKERPS | awk '{print $2}')
                DOCKERID=$(echo $DOCKERPS | awk '{print $1}')
                if (( ${#DOCKERVOLNAME} )); then
                    printf "%50s${Yellow}%30s${NC}\n"   \
                        "Scanning for $vol... "         \
                        "[ $DOCKERID:$DOCKERVOLNAME ]"                      | boxes.sh
                else
                    printf "%50s${Green}%30s${NC}\n"    \
                        "Scanning for $vol... " "[ Not orphaned. ]"         | boxes.sh
                fi
                a_PVOLS+=($DOCKERID)
            done
            echo ""                                                         | boxes.sh
            for VOL in ${a_PVOLS[@]} ; do
                printf "${Cyan}%50s${Yellow}%30s${NC}\n"    \
                        "Removing" " [ $VOL ]"                              | boxes.sh
                docker stop $VOL   > dc.out
                cat dc.out                                                  | boxes.sh
                docker rm -vf $VOL > dc.out
                cat dc.out                                                  | boxes.sh
            done
        windowBottom
    fi

title -d 1  "Destroying persistent volumes" \
            "from  ./docker-compose_dev.yml"
        echo "Do you want to also remove persistent volumes? [y/n]"             | ./boxes.sh
        windowBottom
        old_stty_cfg=$(stty -g)
        stty raw -echo ; REPLY=$(head -c 1) ; stty $old_stty_cfg
        echo -en "\033[2A\033[2K"
        # read -p  " " -n 1 -r REPLY
        if [[ $REPLY =~ ^[Yy]$ ]] ; then
            printf "Removing persistent volumes...\n"                           | ./boxes.sh ${Yellow}
            echo "This might take a few minutes... please be patient."          | ./boxes.sh ${Yellow}
            windowBottom
            docker-compose -f docker-compose_dev.yml --no-ansi -f docker-compose -f docker-compose_dev.yml.yml down -v >& dc.out >/dev/null
            echo -en "\033[2A\033[2K"
            cat dc.out | ./boxes.sh
            echo "Removing ./FS tree"                                           | ./boxes.sh
            rm -fr ./FS
        else
            printf "Keeping persistent volumes...\n"                            | ./boxes.sh ${Yellow}
            echo "This might take a few minutes... please be patient."          | ./boxes.sh ${Yellow}
            windowBottom
            docker-compose -f docker-compose_dev.yml --no-ansi -f docker-compose -f docker-compose_dev.yml.yml down >& dc.out >/dev/null
            echo -en "\033[2A\033[2K"
            cat dc.out | ./boxes.sh
        fi
windowBottom



# title -d 1 "Destroying pfcon containerized development environment" "from ./docker-compose -f docker-compose_dev.yml.yml"
# windowBottom

# title -d 1 "Stopping services..."
#     docker-compose -f docker-compose_dev.yml stop
# windowBottom

# title -d 1 "Removing all containers..."
#     docker-compose -f docker-compose_dev.yml rm -vf
# windowBottom

# title -d 1 "Removing any orphans..."
#     a_VOLS=(
#         "pfcon_swift_storage"
#         "pman"
#         "pfioh"
#         "/pfcon"
#     )
#     a_PVOLS=()
#     for vol in ${a_VOLS[@]}; do
#         SCANTXT=$(printf "Scanning for '%s'... " "$vol")
#         printf "%50s" "$SCANTXT"
#         DOCKERPS=$(docker ps -a | grep -v CONTAINER | grep $vol)
#         DOCKERVOLNAME=$(echo $DOCKERPS | awk '{print $2}')
#         DOCKERID=$(echo $DOCKERPS | awk '{print $1}')
#         if (( ${#DOCKERVOLNAME} )); then
#             printf "${Yellow}[ %s ]${NC}\n" "$DOCKERID:$DOCKERVOLNAME"
#         else
#             printf "${Green}[ Not orphaned. ]${NC}\n"
#         fi
#         a_PVOLS+=($DOCKERID)
#     done
#     printf "\n"
#     for VOL in ${a_PVOLS[@]} ; do
#         printf "${Cyan}Removing ${Yellow}[ $VOL ]${Cyan}${NC}\n"
#         docker stop $VOL >/dev/null && docker rm -vf $VOL > /dev/null
#     done
# windowBottom

# title -d 1 "Destroying persistent volumes..."
#     basedir=`pwd | xargs basename | awk '{print tolower($0)}'`
#     a_VOLS=(
#         "pfcon_swift_storage"
#     )
#     a_PVOLS=()
#     for vol in ${a_VOLS[@]}; do
#         SCANTXT=$(printf "Scanning for '%s'... " "$vol")
#         printf "%50s" "$SCANTXT"
#         DOCKERVOLNAME=$(docker volume ls | grep -v DRIVER | awk {'print $2'} | grep $vol)
#         if (( ${#DOCKERVOLNAME} )); then
#             printf "${Green}[ %s ]${NC}\n" "$DOCKERVOLNAME"
#         else
#             printf "${Red}[ Not found. ]${NC}\n"
#         fi
#         a_PVOLS+=($DOCKERVOLNAME)
#     done
#     printf "\n"
#     for VOL in ${a_PVOLS[@]} ; do
#         printf "${Cyan}Do you want to remove persistent volume ${Green}[ $VOL ]${Cyan}?${NC}"
#         read -p  " [y/n] " -n 1 -r
#         echo
#         if [[ $REPLY =~ ^[Yy]$ ]] ; then
#             docker volume rm $VOL
#         fi
#     done
# windowBottom

title -d 1 "Stopping swarm cluster..."
    docker swarm leave --force >dc.out 2>dc.out
    cat dc.out                                                              | ./boxes.sh
windowBottom
