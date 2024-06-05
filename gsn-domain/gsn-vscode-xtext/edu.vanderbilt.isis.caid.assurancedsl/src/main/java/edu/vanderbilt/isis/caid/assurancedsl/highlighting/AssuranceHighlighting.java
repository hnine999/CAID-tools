package edu.vanderbilt.isis.caid.assurancedsl.highlighting;

import com.google.inject.Inject;
import org.eclipse.emf.ecore.EObject;
import org.eclipse.emf.ecore.EStructuralFeature;
import org.eclipse.xtext.ide.editor.syntaxcoloring.DefaultSemanticHighlightingCalculator;
import org.eclipse.xtext.ide.editor.syntaxcoloring.HighlightingStyles;
import org.eclipse.xtext.ide.editor.syntaxcoloring.IHighlightedPositionAcceptor;
import org.eclipse.xtext.util.CancelIndicator;
import edu.vanderbilt.isis.caid.assurancedsl.services.AssuranceGrammarAccess;
import edu.vanderbilt.isis.caid.assurancedsl.assurance.ALLNodes;
import edu.vanderbilt.isis.caid.assurancedsl.assurance.AssuranceModel;
import edu.vanderbilt.isis.caid.assurancedsl.assurance.AssumptionNode;
import edu.vanderbilt.isis.caid.assurancedsl.assurance.AssumptionNodeRef;
import edu.vanderbilt.isis.caid.assurancedsl.assurance.AssuranceFactory;
import edu.vanderbilt.isis.caid.assurancedsl.assurance.AssurancePackage;
import edu.vanderbilt.isis.caid.assurancedsl.assurance.BaseNode;
import edu.vanderbilt.isis.caid.assurancedsl.assurance.ContextNode;
import edu.vanderbilt.isis.caid.assurancedsl.assurance.ContextNodeRef;
import edu.vanderbilt.isis.caid.assurancedsl.assurance.Description;
import edu.vanderbilt.isis.caid.assurancedsl.assurance.GSNDefinition;
import edu.vanderbilt.isis.caid.assurancedsl.assurance.GoalDetails;
import edu.vanderbilt.isis.caid.assurancedsl.assurance.GoalNode;
import edu.vanderbilt.isis.caid.assurancedsl.assurance.GoalNodeRef;
import edu.vanderbilt.isis.caid.assurancedsl.assurance.JustificationNode;
import edu.vanderbilt.isis.caid.assurancedsl.assurance.JustificationNodeRef;
import edu.vanderbilt.isis.caid.assurancedsl.assurance.SolutionNode;
import edu.vanderbilt.isis.caid.assurancedsl.assurance.SolutionNodeRef;
import edu.vanderbilt.isis.caid.assurancedsl.assurance.StrategyDetails;
import edu.vanderbilt.isis.caid.assurancedsl.assurance.StrategyNode;
import edu.vanderbilt.isis.caid.assurancedsl.assurance.StrategyNodeRef;
import edu.vanderbilt.isis.caid.assurancedsl.assurance.Summary;
import edu.vanderbilt.isis.caid.assurancedsl.assurance.URIA;
import edu.vanderbilt.isis.caid.assurancedsl.assurance.LabelInfo;
import edu.vanderbilt.isis.caid.assurancedsl.assurance.UUIDType;
import edu.vanderbilt.isis.caid.assurancedsl.assurance.impl.AssuranceFactoryImpl;
import edu.vanderbilt.isis.caid.assurancedsl.assurance.impl.AssurancePackageImpl;
import edu.vanderbilt.isis.caid.assurancedsl.assurance.impl.SolutionNodeImpl;
import org.eclipse.xtext.Keyword;



public class AssuranceHighlighting extends DefaultSemanticHighlightingCalculator {

     @Inject
	 private AssuranceGrammarAccess assuranceGrammarAccess;


    protected boolean highlightElement(EObject object, IHighlightedPositionAcceptor acceptor,
        CancelIndicator cancelIndicator) {
            return true;
        // if (object instanceof Summary) {
        //     Keyword k = assuranceGrammarAccess.getSummaryAccess().getSummaryKeyword_0();
        //     acceptor.addPosition(0, 10,HighlightingStyles.KEYWORD_ID);
        //     return true;
        //     //highlightFeature(acceptor, object, AssurancePackage.eINSTANCE.eClass().getEStructuralFeature(AssurancePackage.SUMMARY__INFO), HighlightingStyles.INVALID_TOKEN_ID);
        //     //return false;
        // }
        // return super.highlightElement(object, acceptor, cancelIndicator);
    }

}