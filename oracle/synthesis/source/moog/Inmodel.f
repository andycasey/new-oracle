
      subroutine inmodel 
c******************************************************************************
c     This subroutine reads in the model 
c****************************************************************************** 

      implicit real*8 (a-h,o-z) 
      include 'Atmos.com'
      include 'Linex.com'
      include 'Mol.com'
      include 'Quants.com'
      include 'Factor.com'
      include 'Dummy.com'
      include 'Pstuff.com'
      real*8 kaprefmass(100)
      real*8 bmol(110)
      character list*80, list2*70
      integer append


c*****Read in the key word to define the model type
      wavref = 5000.0
      modelnum = modelnum + 1
c      rewind nfmodel
cc      read (nfmodel,2001) modtype
cc      write (nf1out,1010) modtype
cc      if (modtype .eq. 'begn      ' .or.  modtype .eq. 'BEGN      ') 
cc     .   write (nf1out,1011)


c*****Read a comment line (usually describing the model)
cc      read (nfmodel,2002) moditle


c*****Read the number of depth points
cc      read (nfmodel,2002) list
cc      list2 = list(11:)
cc      read (list2,*) ntau
      if (ntau .gt. 100) then
         if (debug .gt. 0) write (array,1012)
cc         call prinfo (10)
         stop
      endif

      if (modtype .eq. 'WEBMARCS') then
         do i=1,ntau
            tauref(i) = photospheric_structure(i, 1)
            t(i) = photospheric_structure(i, 2)
            ne(i) = photospheric_structure(i, 3)
            pgas(i) = photospheric_structure(i, 4)
         enddo
         rhox(:) = 0.0

      elseif (modtype .eq. 'KURUCZ   ') then
         do i=1,ntau
            rhox(i) = photospheric_structure(i, 1)
            t(i) = photospheric_structure(i, 2)
            pgas(i) = photospheric_structure(i, 3)
            ne(i) = photospheric_structure(i, 4)
            kaprefmass(i) = photospheric_structure(i, 5)
         enddo
      else
         write (*,1001)
         stop
      endif


c*****EITHER: Read in a model from the output of the experimental new
c     MARCS code.  This modtype is called "NEWMARCS".  On each line 
c     the numbers are:
c     tau(5000), t, pe, pgas, rho,  model microtrubulent velocity,
c     and mean opacity (cm^2/gm) at the reference wavelength (5000A).
cc      if (modtype .eq. 'NEWMARCS  ') then
cc         read (nfmodel,*) wavref    
cc         do i=1,ntau
cc            read (nfmodel,*) tauref(i),t(i),ne(i),pgas(i),rho(i),
cc     .                         vturb(1),kaprefmass(i)
cc         enddo
c*****OR: Read in a model from the output of the on-line new
c     MARCS code.  This modtype is called "WEBMARCS".  On each line
c     the numbers are:
c     layer number (not needed), log{tau(Rosseland)} (not needed),
c     log{tau(5000)}, depth, t, pe, pgas, prad (not read in) and
c     pturb (not read in)
cc      elseif (modtype .eq. 'WEBMARCS') then
cc         read (nfmodel,*) wavref
cc         do i=1,ntau
cc            read (nfmodel,*) k, dummy1(k), tauref(i), dummy2(k), t(i),
cc     .                       ne(i), pgas(i)
cc         enddo
c*****OR: Read in a model from an alternative form of on-line new
c     MARCS code.  This modtype is called "WEB2MARC".  On each line
c     the numbers are:
c     atmospheric layer number (not needed), log{tau(5000)}, t, 
c     log(Pe), log(Pgas), rhox
cc      elseif (modtype .eq. 'WEB2MARC') then
cc         read (nfmodel,*) wavref
cc         do i=1,ntau
cc            read (nfmodel,*) k,tauref(i),t(i),ne(i),pgas(i),rhox(i)
cc         enddo
c     OR: Read in a model from the output of the ATLAS code.  This
c     modtype is called "KURUCZ".  On each line the numbers are:
c     rhox, t, pgas, ne, and Rosseland mean opacity (cm^2/gm), and
c     two numbers not used by MOOG.  
cc      elseif (modtype .eq. 'KURUCZ    ') then
cc         do i=1,ntau
cc            read (nfmodel,*) rhox(i),t(i),pgas(i),ne(i),kaprefmass(i)
cc         enddo
c     OR: Read in a model from the output of the NEXTGEN code.  This
c     modtype is called "NEXTGEN".  These models have tau scaled at a 
c     specific wavelength that is read in before the model. MOOG will 
c     need to generate the opacities internally.On each line the numbers 
c     are: tau, t, pgas, pe, density, mean molecular weight, two numbers
c     not used by MOOG, and Rosseland mean opacity (cm^2/gm).
cc      elseif (modtype .eq. 'NEXTGEN   ') then
cc         read (nfmodel,*) wavref
cc         do i=1,ntau
cc            read (nfmodel,*) tauref(i),t(i),pgas(i),ne(i), rho(i),  
cc     .                       molweight(i), x2, x3, kaprefmass(i)
cc         enddo
c     OR: Read in a model from the output of the MARCS code.  This modtype
c     type is called "BEGN".  On each line the numbers are:
c     tauross, t, log(pg), log(pe), mol weight, and kappaross.
cc      elseif (modtype .eq. 'BEGN      ') then
cc         do i=1,ntau
cc            read (nfmodel,*) tauref(i),t(i),pgas(i),ne(i),
cc     .                          molweight(i),  kaprefmass(i)
cc         enddo
c     OR: Read in a model generated from ATLAS, but without accompanying
c     opacities.  MOOG will need to generate the opacities internally,
c     using a reference wavelength that it reads in before the model.
cc      elseif (modtype .eq. 'KURTYPE') then
cc         read (nfmodel,*) wavref    
cc         do i=1,ntau
cc            read (nfmodel,*) rhox(i),t(i),pgas(i),ne(i)
cc         enddo
c     OR: Read in a model generated from ATLAS, with output generated
c     in Padova.  The columns are in somewhat different order than normal
cc      elseif (modtype .eq. 'KUR-PADOVA') then
cc         read (nfmodel,*) wavref
cc         do i=1,ntau
cc            read (nfmodel,*) tauref(i),t(i),kaprefmass(i),
cc     .                         ne(i),pgas(i),rho(i)
cc         enddo
c     OR: Read in a generic model that has a tau scale at a specific 
c     wavelength that is read in before the model.  
c     MOOG will need to generate the opacities internally.
cc      elseif (modtype .eq. 'GENERIC   ') then
cc         read (nfmodel,*) wavref    
cc         do i=1,ntau
cc            read (nfmodel,*) tauref(i),t(i),pgas(i),ne(i)
cc         enddo
c     OR: quit in utter confusion if those model types are not specified
cc      else
cc         write (*,1001)
cc         stop
cc      endif


c*****Compute other convenient forms of the temperatures
      do i=1,ntau
          theta(i) = 5040./t(i)
          tkev(i) = 8.6171d-5*t(i)
          tlog(i) = dlog(t(i))
      enddo


c*****Convert from logarithmic Pgas scales, if needed
      if (pgas(ntau)/pgas(1) .lt. 10.) then
         do i=1,ntau                                                    
            pgas(i) = 10.0**pgas(i)
         enddo
      endif


c*****Convert from logarithmic Ne scales, if needed
      if(ne(ntau)/ne(1) .lt. 20.) then
         do i=1,ntau                                                    
            ne(i) = 10.0**ne(i)
         enddo
      endif


c*****Convert from Pe to Ne, if needed
      if(ne(ntau) .lt. 1.0e7) then
         do i=1,ntau                                                    
            ne(i) = ne(i)/1.38054d-16/t(i)
         enddo
      endif


c*****compute the atomic partition functions
      do j=1,95
         elem(j) = dble(j)
         call partfn (elem(j),j)
      enddo


c*****Read the microturbulence (either a single value to apply to 
c     all layers, or a value for each of the ntau layers). 
c     Conversion to cm/sec from km/sec is done if needed
cc      read (nfmodel,2003) (vturb(i),i=1,6)
cc      if (vturb(2) .ne. 0.) then
cc         read (nfmodel,2003) (vturb(i),i=7,ntau) 
cc      else
cc         do i=2,ntau                                                    
cc            vturb(i) = vturb(1)
cc         enddo
cc      endif
      do i=2,ntau
         vturb(i) = vturb(1)
      enddo

      if (vturb(1) .lt. 100.) then
         if (debug .gt. 0) write (moditle(55:62),1008) vturb(1)
         do i=1,ntau
            vturb(i) = 1.0e5*vturb(i)
         enddo
      else
         if (debug .gt. 0) write (moditle(55:62),1008) vturb(1)/1.0e5
      endif


c*****Read in the abundance data, storing the original abundances in xabu
c*****The abundances not read in explicity are taken from the default
c*****solar ones contained in array xsolar.
cc      read (nfmodel,2002) list
cc      list2 = list(11:)
cc      read (list2,*) natoms,abscale
cc      write (moditle(63:73),1009) abscale
cc      if(natoms .ne. 0) 
cc     .         read (nfmodel,*) (element(i),logepsilon(i),i=1,natoms) 
cc    (The element, logepsilon arrays are entered in MyAbfind now.)

      xhyd = 10.0**xsolar(1)
      xabund(1) = 1.0
      xabund(2) = 10.0**xsolar(2)/xhyd
      do i=3,95                                                      
         xabund(i) = 10.0**(xsolar(i)+abscale)/xhyd
         xabu(i) = xabund(i)
      enddo
      if (natoms .ne. 0) then
         do i=1,natoms                                                  
            xabund(idint(element(i))) = 10.0**logepsilon(i)/xhyd
            xabu(idint(element(i))) = 10.0**logepsilon(i)/xhyd
         enddo
      endif

c*****Compute the mean molecular weight, ignoring molecule formation
c     in this approximation (maybe make more general some day?)
      wtnum = 0.
      wtden = 0.
      do i=1,95
         wtnum = wtnum + xabund(i)*xam(i)
         wtden = wtden + xabund(i)
      enddo
      wtmol = wtnum/(xam(1)*wtden)
      nomolweight = 0
cc      if (modtype .eq. 'BEGN      ' .or. modtype .eq. 'NEXTGEN   ') then
cc         nomolweight = 1
cc      endif
      if (nomolweight .ne. 1) then
         do i=1,ntau
             molweight(i) = wtmol
         enddo
      endif

c*****Compute the density 
      if (modtype .ne. 'NEXTGEN   ') then
         do i=1,ntau                                                    
            rho(i) = pgas(i)*molweight(i)*1.6606d-24/(1.38054d-16*t(i))
         enddo
      endif


c*****Calculate the fictitious number density of hydrogen
c     Note:  ph = (-b1 + dsqrt(b1*b1 - 4.0*a1*c1))/(2.0*a1)
      iatom = 1
      call partfn (dble(iatom),iatom)
      do i=1,ntau    
         th = 5040.0/t(i)         
         ah2 = 10.0**(-(12.7422+(-5.1137+(0.1145-0.0091*th)*th)*th))
         a1 = (1.0+2.0*xabund(2))*ah2
         b1 = 1.0 + xabund(2)
         c1 = -pgas(i)         
         ph = (-b1/2.0/a1)+dsqrt((b1**2/(4.0*a1*a1))-(c1/a1))
         nhtot(i) = (ph+2.0*ph*ph*ah2)/(1.38054d-16*t(i))
      enddo


c*****Molecular equilibrium called here.
c     First, a default list of ions and molecules is considered. Then the 
c     user's list is read in. A check is performed to see if any of these 
c     species need to be added. If so, then they are appended to the 
c     default list. The molecular equilibrium routine is then called.
c     Certain species are important for continuous opacities and damping
c     calculations - these are read from the equilibrium solution and 
c     saved.


c*****Set up the default molecule list
      if (molset .eq. 0) then
         nmol = 21
      else
         nmol = 57
      endif
      if     (molset .eq. 0) then
         do i=1,110
            amol(i) = smallmollist(i)
         enddo
      elseif (molset .eq. 1) then
         do i=1,110
            amol(i) = largemollist(i)
         enddo
      else
         array = 'molset = 0 or 1 only; I quit!'
         print *, array
cc         call putasci (29,6)
         stop
      endif


c*****Read in the names of additional molecules to be used in 
c     molecular equilibrium if needed.
      if (debug .gt. 0) print *, "IGNORING ATMOSPHERE MOLECULES"
cc      read (nfmodel,2002,end=101) list
cc      list2 = list(11:)
cc      read (list2,*) moremol
cc      if (moremol .ne. 0) then
cc         read (nfmodel,*) (bmol(i),i=1,moremol)
cc         append = 1
cc         do k=1,moremol
cc            do l=1,nmol
cc               if (nint(bmol(k)) .eq. nint(amol(l))) 
cc     .         append = 0  
cc            enddo
cc            if (append .eq. 1) then 
cc               nmol = nmol + 1
cc               amol(nmol) = bmol(k)
cc            endif
cc            append = 1
cc         enddo  
cc      endif


c*****do the general molecular equilibrium
cc101   call eqlib
      call eqlib


c     In the number density array "numdens", the elements denoted by
c     the first subscripts are named in at the ends of the assignment
c     lines; at present these are the only ones needed for continuous 
c     opacities
c     
      do i=1,ntau
         numdens(1,1,i) = xamol(1,i)                                    H I
         numdens(1,2,i) = xmol(1,i)                                     H II
         numdens(2,1,i) = xamol(2,i)                                    He I
         numdens(2,2,i) = xmol(2,i)                                     Hi II
         numdens(3,1,i) = xamol(3,i)                                    C I
         numdens(3,2,i) = xmol(3,i)                                     C II
         numdens(4,1,i) = xamol(6,i)                                    Mg I
         numdens(4,2,i) = xmol(6,i)                                     Mg II
         numdens(5,1,i) = xamol(7,i)                                    Al I
         numdens(5,2,i) = xmol(7,i)                                     Al II
         numdens(6,1,i) = xamol(8,i)                                    Si I
         numdens(6,2,i) = xmol(8,i)                                     Si II
         numdens(7,1,i) = xamol(16,i)                                   Fe I
         numdens(7,2,i) = xmol(16,i)                                    Fe II
         numdens(8,1,i) = xmol(17,i)                                    H_2
      enddo



c*****SPECIAL NEEDS: for NEWMARCS models, to convert kaprefs to our units
cc      if (modtype .eq. 'NEWMARCS  ') then
cc         do i=1,ntau
cc            kapref(i) = kaprefmass(i)*rho(i)
cc         enddo
c     SPECIAL NEEDS: for KURUCZ models, to create the optical depth array,
c     and to convert kaprefs to our units
cc      elseif (modtype .eq. 'KURUCZ    ') then
      if (modtype .eq. 'KURUCZ    ') then
         if (debug .gt. 0) print *, "doing special needs"
         first = rhox(1)*kaprefmass(1)
         tottau = rinteg(rhox,kaprefmass,tauref,ntau,first) 
         tauref(1) = first
         do i=2,ntau
            tauref(i) = tauref(i-1) + tauref(i)
         enddo
         do i=1,ntau
            kapref(i) = kaprefmass(i)*rho(i)
         enddo
c     SPECIAL NEEDS: for NEXTGEN models, to convert kaprefs to our units
cc      elseif (modtype .eq. 'NEXTGEN   ') then
cc         do i=1,ntau                                                    
cc            kapref(i) = kaprefmass(i)*rho(i)
cc         enddo
c     SPECIAL NEEDS: for BEGN models, to convert kaprefs to our units
cc      elseif (modtype .eq. 'BEGN      ') then
cc         do i=1,ntau                                                    
cc            kapref(i) = kaprefmass(i)*rho(i)
cc         enddo
c     SPECIAL NEEDS: for KURTYPE models, to create internal kaprefs,
c     and to compute taurefs from the kaprefs converted to mass units
cc      elseif (modtype .eq. 'KURTYPE   ') then
cc         call opacit (1,wavref)
cc         do i=1,ntau                                                    
cc            kaprefmass(i) = kapref(i)/rho(i)
cc         enddo
cc         first = rhox(1)*kaprefmass(1)
cc         tottau = rinteg(rhox,kaprefmass,tauref,ntau,first) 
cc         tauref(1) = first
cc         do i=2,ntau
cc            tauref(i) = tauref(i-1) + tauref(i)
cc         enddo
c     SPECIAL NEEDS: for NEWMARCS models, to convert kaprefs to our units
cc      elseif (modtype .eq. 'KUR-PADOVA') then
cc         do i=1,ntau
cc            kapref(i) = kaprefmass(i)*rho(i)
cc         enddo
c     SPECIAL NEEDS: for generic models, to create internal kaprefs,
      elseif (modtype .eq. 'GENERIC   ' .or.
     .        modtype .eq. 'WEBMARCS  ' .or.
     .        modtype .eq. 'WEB2MARC  ') then
         call opacit (1,wavref)
      endif


c*****Convert from logarithmic optical depth scales, or vice versa.
c     xref will contain the log of the tauref
      if(tauref(1) .lt. 0.) then
         do i=1,ntau                                                    
            xref(i) = tauref(i)
            tauref(i) = 10.0**xref(i)
         enddo
      else
         do i=1,ntau                                                    
            xref(i) = dlog10(tauref(i))
         enddo
      endif


c*****Write information to output files
      if (modprintopt .lt. 1 .or. debug .lt. 1) return
      write (nf1out,1002) moditle
      do i=1,ntau
         dummy1(i) = dlog10(pgas(i))
         dummy2(i) = dlog10(ne(i)*1.38054d-16*t(i))
      enddo
      write (nf1out,1003) wavref,(i,xref(i),tauref(i),t(i),dummy1(i),
     .                    pgas(i),dummy2(i),ne(i),vturb(i),i=1,ntau)
      write (nf1out,1004)
      do i=1,95
         dummy1(i) = dlog10(xabund(i)) + 12.0
      enddo
      write (nf1out,1005) (names(i),i,dummy1(i),i=1,95)
      write (nf1out,1006) modprintopt, molopt, linprintopt, fluxintopt
      write (nf1out,1007) (kapref(i),i=1,ntau)
      return


c*****format statements
2001  format (a10)
2002  format (a80)
2003  format (6d13.0)
1001  format('permitted model types are:'/'KURUCZ, BEGN, ',
     .       'KURTYPE, KUR-PADOVA, NEWMARCS, WEBMARCS, NEXTGEN, ',
     .       'WEB2MARC, or GENERIC'/ 'MOOG quits!')
1002  format (/'MODEL ATMOSPHERE HEADER:'/a80/)
1003  format ('INPUT ATMOSPHERE QUANTITIES', 10x,
     .        '(reference wavelength =',f10.2,')'/3x, 'i', 2x, 'xref',
     .        3x, 'tauref', 7x, 'T', 6x, 'logPg', 4x, 'Pgas',
     .        6x, 'logPe', 5x, 'Ne', 9x, 'Vturb'/
     .        (i4, 0pf6.2, 1pd11.4, 0pf9.1, f8.3, 1pd11.4, 0pf8.3,
     .        1pd11.4, d11.2))
1004  format (/'INPUT ABUNDANCES: (log10 number densities, log H=12)'/
     .       '      Default solar abundances: Asplund et al. 2009')
1005  format (5(3x,a2, '(',i2,')=', f5.2))
1006  format (/'OPTIONS: atmosphere = ', i1, 5x, 'molecules  = ', i1/
     .        '         lines      = ', i1, 5x, 'flux/int   = ', i1)
1007  format (/'KAPREF ARRAY:'/(6(1pd12.4)))
1008  format ('vt=', f5.2)
1009  format (' M/H=', f5.2)
1010  format (13('-'),'MOOG OUTPUT FILE', 10('-'),
     .        '(MOOG version from 01/28/09)', 13('-')//
     .        'THE MODEL TYPE: ', a10)
1011  format ('   The Rosseland opacities and optical depths have ',
     .        'been read in')
1012  format ('HOUSTON, WE HAVE MORE THAN 100 DEPTH POINTS! I QUIT!')


      end

